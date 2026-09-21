/**
 * Tradiesignal :: collect-eplanning
 * =================================
 * Supabase Edge Function. Pulls one ePlanning service for one council,
 * upserts into `applications`, links to `projects`, and records the run.
 *
 * Invoke (pg_cron / scheduler):
 *   POST /functions/v1/collect-eplanning
 *   { "service": "OnlineCC", "council": "Newcastle City Council", "days": 45 }
 *
 * Protocol notes — these were established against the live API and are easy to
 * get wrong:
 *   - It is a GET. POST to the same path returns 404, not 405.
 *   - PageSize, PageNumber and filters travel as HTTP HEADERS, not query params.
 *     A `filters` query parameter returns 400.
 *   - CouncilName must match the API's Appendix 1 spelling EXACTLY. A near miss
 *     returns HTTP 200 with zero records — a silent failure. We assert against
 *     the previous run and mark the run `partial` rather than `success`.
 *   - Location[].X is LONGITUDE, Location[].Y is LATITUDE. Getting this the
 *     wrong way round puts the entire Hunter in the Indian Ocean.
 */

import { createClient, SupabaseClient } from "jsr:@supabase/supabase-js@2";

const API_ROOT = "https://api.apps1.nsw.gov.au/eplanning/data/v0";
const PAGE_SIZE = 100;
const MAX_RETRIES = 4;
const THROTTLE_MS = 300;

type Service = "OnlineDA" | "OnlineCDC" | "OnlineCC";

const SOURCE_KEY: Record<Service, string> = {
  OnlineDA: "eplanning_da",
  OnlineCDC: "eplanning_cdc",
  OnlineCC: "eplanning_cc",
};

interface Location {
  FullAddress?: string;
  X?: string;          // longitude
  Y?: string;          // latitude
  Suburb?: string;
  Postcode?: string;
  Lot?: { Lot?: string; PlanLabel?: string }[];
}

interface ApplicationRecord {
  PlanningPortalApplicationNumber?: string;
  CouncilApplicationNumber?: string;
  CertifierApplicationNumber?: string;
  ApplicationType?: string;
  ApplicationStatus?: string;
  CostOfDevelopment?: number;
  NumberOfNewDwellings?: number;
  UnitsProposed?: number;
  NumberOfStoreys?: number;
  StoreysProposed?: number;
  NumberOfProposedLots?: number;
  ProposedLots?: number;
  ProposedGrossFloorArea?: number;
  ExistingGrossFloorArea?: number;
  LandArea?: number;
  CurrentBuildingUse?: string;
  ProposedBuildingUse?: string;
  BuilderLegalName?: string;
  BuilderTradingName?: string;
  LodgementDate?: string;
  SubmissionDate?: string;
  DateSubmitted?: string;
  DeterminationDate?: string;
  DateLastUpdated?: string;
  AssessmentExhibitionStartDate?: string;
  AssessmentExhibitionEndDate?: string;
  DeterminationAuthority?: string;
  AccompaniedByVPAFlag?: string;
  DevelopmentSubjectToSICFlag?: string;
  SubdivisionProposedFlag?: string;
  Council?: { CouncilName?: string };
  DevelopmentType?: { DevelopmentType?: string }[];
  BuildingCodeClass?: { BuildingCodeClass?: string }[];
  Location?: Location[];
}

interface ApiPage {
  PageSize: number;
  PageNumber: number;
  TotalPages: number;
  TotalCount: number;
  Application: ApplicationRecord[];
}

// ---------------------------------------------------------------------------
// fetch
// ---------------------------------------------------------------------------

async function fetchPage(
  service: Service,
  filters: Record<string, unknown>,
  page: number,
): Promise<ApiPage> {
  const headers = {
    PageSize: String(PAGE_SIZE),
    PageNumber: String(page),
    filters: JSON.stringify({ filters }),
    Accept: "application/json",
    "User-Agent": "Tradiesignal/1.0 (+https://tradiesignal.com.au) open-data collector",
  };

  let lastError: unknown;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(`${API_ROOT}/${service}`, { method: "GET", headers });
      if (res.ok) return await res.json() as ApiPage;

      // 4xx other than 429 will not fix themselves.
      if (res.status !== 429 && res.status >= 400 && res.status < 500) {
        throw new Error(`${service} p${page}: HTTP ${res.status} ${await res.text()}`);
      }
      lastError = new Error(`HTTP ${res.status}`);
    } catch (err) {
      lastError = err;
      if (String(err).includes("HTTP 4")) throw err;
    }
    await new Promise((r) => setTimeout(r, 2 ** attempt * 1000));
  }
  throw new Error(`${service} page ${page} failed after ${MAX_RETRIES}: ${lastError}`);
}

// ---------------------------------------------------------------------------
// normalise
// ---------------------------------------------------------------------------

function isoDate(v?: string): string | null {
  if (!v) return null;
  const m = String(v).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;
  const d = String(v).match(/^(\d{2})\/(\d{2})\/(\d{4})/);   // dd/mm/yyyy
  return d ? `${d[3]}-${d[2]}-${d[1]}` : null;
}

/** Must stay byte-identical to normalise_address() in 003_functions.sql. */
function normaliseAddress(addr: string): string {
  return (addr || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

const DEAD = new Set(["withdrawn", "rejected"]);

function stageOf(service: Service, status: string, hasExhibition: boolean): string {
  const s = (status || "").trim().toLowerCase();
  if (DEAD.has(s)) return "withdrawn";
  if (service === "OnlineCC") return s === "determined" ? "cc_determined" : "cc_lodged";
  if (service === "OnlineCDC") return s === "approved" ? "cdc_approved" : "cdc_lodged";
  if (s === "determined") return "da_determined";
  if (s === "additional information requested") return "da_info";
  if (s === "on exhibition") return "da_exhibition";
  if (s === "under assessment") return hasExhibition ? "da_exhibition" : "da_assessment";
  return "da_lodged";
}

/**
 * A builder field is only useful if it names a builder. Certifiers, surveyors
 * and planning consultants land in this field often enough to poison the
 * watchlist if you trust it blindly.
 */
const NON_BUILDER = [
  "certifier", "certification", "surveyor", "consult",
  "engineering services", "town planning", "planning pty", "architect",
];

function cleanBuilder(record: ApplicationRecord): string | null {
  const raw = (record.BuilderTradingName || record.BuilderLegalName || "").trim();
  if (!raw) return null;
  const low = raw.toLowerCase();
  return NON_BUILDER.some((t) => low.includes(t)) ? null : raw;
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

Deno.serve(async (req: Request) => {
  const started = Date.now();

  const supabase: SupabaseClient = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,   // service role: bypasses RLS
    { auth: { persistSession: false } },
  );

  let runId: string | null = null;

  try {
    const body = await req.json().catch(() => ({}));
    const service: Service = body.service ?? "OnlineDA";
    const councilName: string = body.council;
    const days: number = body.days ?? 45;

    if (!councilName) throw new Error("council is required");
    if (!(service in SOURCE_KEY)) throw new Error(`unknown service ${service}`);

    const [{ data: source }, { data: council }] = await Promise.all([
      supabase.from("data_sources").select("id, key")
        .eq("key", SOURCE_KEY[service]).single(),
      supabase.from("councils").select("id, name").eq("name", councilName).single(),
    ]);
    if (!source) throw new Error(`data_source ${SOURCE_KEY[service]} missing`);
    if (!council) throw new Error(`council "${councilName}" not seeded — check exact spelling`);

    const from = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
    const to = new Date().toISOString().slice(0, 10);

    const { data: run } = await supabase.from("ingestion_runs").insert({
      data_source_id: source.id,
      council_id: council.id,
      window_from: from,
      window_to: to,
      status: "running",
    }).select("id").single();
    runId = run!.id;

    // ---- fetch every page ------------------------------------------------
    const filters = { CouncilName: [councilName], LodgementDateFrom: from };
    const records: ApplicationRecord[] = [];
    let page = 1, totalPages = 1, totalCount = 0;

    while (page <= totalPages) {
      const payload = await fetchPage(service, filters, page);
      if (page === 1) {
        totalPages = payload.TotalPages ?? 0;
        totalCount = payload.TotalCount ?? 0;
        if (totalCount === 0) break;
      }
      records.push(...(payload.Application ?? []));
      page++;
      if (page <= totalPages) await new Promise((r) => setTimeout(r, THROTTLE_MS));
    }

    // ---- silent-zero guard ----------------------------------------------
    // HTTP 200 with no records is what a misspelled council name looks like.
    // Compare against the last successful run before believing it.
    let silentZero = false;
    if (records.length === 0) {
      const { data: prior } = await supabase
        .from("ingestion_runs")
        .select("records_fetched")
        .eq("data_source_id", source.id)
        .eq("council_id", council.id)
        .eq("status", "success")
        .order("started_at", { ascending: false })
        .limit(1);
      if (prior?.length && prior[0].records_fetched > 0) silentZero = true;
    }

    // ---- link and upsert -------------------------------------------------
    let created = 0, updated = 0, rejected = 0;

    for (const rec of records) {
      const ref = rec.PlanningPortalApplicationNumber;
      if (!ref) {
        rejected++;
        await supabase.from("ingestion_rejects").insert({
          run_id: runId, reason: "no PlanningPortalApplicationNumber", raw: rec,
        });
        continue;
      }

      const loc = (rec.Location ?? [])[0] ?? {};
      const address = (loc.FullAddress ?? "").trim();
      const lot = (loc.Lot ?? [])[0];
      const lotRef = lot ? `${lot.Lot ?? ""}/${lot.PlanLabel ?? ""}`.replace(/^\/|\/$/g, "") : null;
      const status = rec.ApplicationStatus ?? "";
      const stage = stageOf(service, status, Boolean(rec.AssessmentExhibitionStartDate));

      // Find or create the project this application belongs to.
      const { data: projectId } = await supabase.rpc("link_project", {
        p_council_id: council.id,
        p_address: address,
        p_lot_ref: lotRef,
      });

      let pid: string | null = projectId as string | null;

      if (!pid) {
        // X is longitude, Y is latitude. Do not swap these.
        const lon = loc.X ? Number(loc.X) : null;
        const lat = loc.Y ? Number(loc.Y) : null;
        const { data: created_p, error } = await supabase.from("projects").insert({
          public_ref: `TS-${council.id}-${ref.replace(/^(PAN|CDC|CFT)-/, "")}`,
          slug: `${(loc.Suburb ?? "hunter").toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${ref.toLowerCase()}`,
          name: address || ref,                      // scorer replaces this
          council_id: council.id,
          address: address || "Address not supplied",
          address_normalised: normaliseAddress(address) || ref,
          suburb: loc.Suburb ?? null,
          postcode: loc.Postcode ?? null,
          lot_ref: lotRef,
          geom: lat && lon ? `SRID=4326;POINT(${lon} ${lat})` : null,
          category: "other",                         // scorer replaces
          filter_group: "Commercial",                // scorer replaces
          stage,
          stage_label: stage,
          status_raw: status,
        }).select("id").single();
        if (error) { rejected++; continue; }
        pid = created_p!.id;
        created++;
      }

      const { error: upsertErr } = await supabase.from("applications").upsert({
        project_id: pid,
        data_source_id: source.id,
        source_ref: ref,
        council_ref: rec.CouncilApplicationNumber ?? rec.CertifierApplicationNumber ?? null,
        service,
        application_type: rec.ApplicationType ?? null,
        status_raw: status,
        stage,
        cost_declared: rec.CostOfDevelopment ?? null,
        date_submitted: isoDate(rec.SubmissionDate ?? rec.DateSubmitted),
        date_lodged: isoDate(rec.LodgementDate),
        date_determined: isoDate(rec.DeterminationDate),
        exhibition_start: isoDate(rec.AssessmentExhibitionStartDate),
        exhibition_end: isoDate(rec.AssessmentExhibitionEndDate),
        determination_authority: rec.DeterminationAuthority ?? null,
        builder_legal_name: rec.BuilderLegalName ?? null,
        builder_trading_name: rec.BuilderTradingName ?? null,
        raw: rec,
        source_updated_at: rec.DateLastUpdated ?? null,
      }, { onConflict: "data_source_id,source_ref" });

      if (upsertErr) rejected++; else updated++;

      // Never let a later revision null out a builder name we already hold.
      const builder = cleanBuilder(rec);
      if (builder && pid) {
        await supabase.from("projects")
          .update({ builder_name: builder })
          .eq("id", pid)
          .is("builder_name", null);
      }
    }

    const status = silentZero || rejected > records.length * 0.05 ? "partial" : "success";

    await supabase.from("ingestion_runs").update({
      status,
      records_fetched: records.length,
      records_new: created,
      records_updated: updated,
      records_rejected: rejected,
      projects_created: created,
      duration_ms: Date.now() - started,
      finished_at: new Date().toISOString(),
      error: silentZero
        ? "Zero records returned for a council that previously returned records. "
          + "Check the CouncilName spelling against the API's Appendix 1 list."
        : null,
    }).eq("id", runId);

    if (status === "success") {
      await supabase.from("data_sources").update({
        last_success_at: new Date().toISOString(),
        consecutive_failures: 0,
      }).eq("id", source.id);
    }

    return Response.json({
      ok: status === "success",
      service, council: councilName, status,
      fetched: records.length, expected: totalCount,
      created, updated, rejected,
      ms: Date.now() - started,
    });

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    if (runId) {
      await supabase.from("ingestion_runs").update({
        status: "failed", error: message,
        duration_ms: Date.now() - started,
        finished_at: new Date().toISOString(),
      }).eq("id", runId);
    }
    console.error("collect-eplanning failed:", message);
    return Response.json({ ok: false, error: message }, { status: 500 });
  }
});
