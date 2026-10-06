function out = netrasetu_analyze(imgPath, outDir)
%NETRASETU_ANALYZE  DR screening pipeline for one fundus image (contract 1.1).
%   out = netrasetu_analyze(imgPath, outDir) returns a struct that jsonencode() serialises into
%   the engine result in docs/CONTRACT.md, Section 6.1. Image artefacts (Grad-CAM, evidence
%   crops, report) are written under outDir and returned as paths.
%
%   M1 STUB: no algorithm runs yet. The image is only checked for readability, and a fixed,
%   contract-valid placeholder result is returned. The placeholder is always REFER with
%   reviewRequired = true, so a stub result can never send a patient home. The real pipeline
%   (nx_quality, nx_enhance, nx_structures, nx_lesions, nx_grade, nx_gradcam, ...) lands in M4.
%
%   Null-valued contract fields are encoded as NaN, which jsonencode writes as null.

    arguments
        imgPath (1,1) string {mustBeFile}
        outDir (1,1) string
    end

    if ~isfolder(outDir)
        mkdir(outDir);
    end

    info = imfinfo(imgPath);
    if isempty(info) || info(1).Width < 1 || info(1).Height < 1
        error("nx:analyze:unreadable", "Cannot read image %s", imgPath);
    end

    cfg = nx_config();

    out = struct();
    out.contractVersion = cfg.contractVersion;
    out.modelVer = cfg.modelVer;
    out.cfgHash = cfg.cfgHash;
    out.decision = "REFER";
    out.reviewRequired = true;

    quality = struct();
    quality.verdict = "accept";
    quality.score = 1.0;
    quality.failureMode = "none";
    quality.phash = "0000000000000000";
    out.quality = quality;

    out.retakeGuidanceKey = NaN;

    % Placeholder posterior (not a model output). Sums to 1; grade is its argmax.
    posterior = [0.05 0.10 0.50 0.25 0.10];
    [~, idx] = max(posterior);
    out.grade = idx - 1;
    out.posterior = posterior;
    out.pReferable = sum(posterior(3:5));
    out.laterality = "unknown";

    out.criteria = struct("key", {}, "grade", {}, "detail", {});
    out.evidence = struct("type", {}, "x", {}, "y", {}, "quadrant", {}, ...
        "distanceToFoveaDD", {}, "cropPath", {}, "criterionKey", {});

    out.gradcamPath = NaN;
    out.llp = NaN;
    out.reportPath = NaN;

    fhir = struct();
    fhir.resourceType = "Bundle";
    fhir.type = "collection";
    fhir.entry = {};
    out.fhirBundle = fhir;
end
