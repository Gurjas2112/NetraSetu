function params = load_simevents_params(paramsPath)
%LOAD_SIMEVENTS_PARAMS  Load District Twin parameters from params.json.
%
%   params = load_simevents_params() reads matlab/simevents/params.json.
%   Inference service times come from scripts/locust_to_simevents.py; other
%   rates must be measured (quality-gate rework, cache hit ratio, triage split).
%
%   graderServiceTimeSeconds defaults to 30 (spec Section 25). Nothing else
%   is invented here — missing required fields raise an error at build time.

arguments
    paramsPath (1,1) string = ""
end

here = fileparts(mfilename("fullpath"));
if paramsPath == ""
    paramsPath = fullfile(here, "params.json");
end

if ~isfile(paramsPath)
    error("load_simevents_params:MissingFile", ...
        "No params file at %s. Copy params.json.example to params.json or run Locust + locust_to_simevents.py.", ...
        paramsPath);
end

raw = jsondecode(fileread(paramsPath));
params = normalizeParams(raw);
params.paramsPath = paramsPath;
end

function params = normalizeParams(raw)
params = struct();
params.source = getfieldOr(raw, "source", "");
params.name = getfieldOr(raw, "name", "");

inf = getfieldOr(raw, "inferenceServiceTimeSeconds", struct());
params.inferenceServiceTimeSeconds = struct( ...
    "p50", getfieldOr(inf, "p50", []), ...
    "p95", getfieldOr(inf, "p95", []));

params.graderServiceTimeSeconds = getfieldOr(raw, "graderServiceTimeSeconds", 30);
params.graderCount = getfieldOr(raw, "graderCount", []);
params.arrivalsPerDay = getfieldOr(raw, "arrivalsPerDay", []);
params.simulationDays = getfieldOr(raw, "simulationDays", 1);
params.reworkRate = getfieldOr(raw, "reworkRate", []);
params.cacheHitRate = getfieldOr(raw, "cacheHitRate", []);
params.referToReviewFraction = getfieldOr(raw, "referToReviewFraction", []);
params.uploadMegabytes = getfieldOr(raw, "uploadMegabytes", []);
params.uplinkMbps = getfieldOr(raw, "uplinkMbps", []);

params.qualityGateSeconds = getfieldOr(raw, "qualityGateSeconds", 5);
end

function v = getfieldOr(s, name, default)
if isstruct(s) && isfield(s, name) && ~isempty(s.(name))
    v = s.(name);
else
    v = default;
end
end
