function out = netrasetu_analyze(imgPath, outDir)
%NETRASETU_ANALYZE  DR screening pipeline for one fundus image (contract 1.1).
%   out = netrasetu_analyze(imgPath, outDir) returns a struct that jsonencode() serialises
%   into the engine result in docs/CONTRACT.md. Artefacts are written under outDir.
%
%   Null-valued contract fields are NaN, which jsonencode writes as null.

    arguments
        imgPath (1,1) string {mustBeFile}
        outDir (1,1) string
    end

    if ~isfolder(outDir)
        mkdir(outDir);
    end

    cfg = nx_config();
    q = nx_quality(imgPath);

    out = struct();
    out.contractVersion = cfg.contractVersion;
    out.modelVer = cfg.modelVer;
    out.cfgHash = cfg.cfgHash;
    out.quality = local_quality(q);
    out.laterality = "unknown";
    out.criteria = {};
    out.evidence = {};
    out.gradcamPath = NaN;
    out.llp = NaN;
    out.reportPath = NaN;
    out.fhirBundle = struct("resourceType", "Bundle", "type", "collection", "entry", {{}});

    if q.verdict == "reject"
        out.decision = "RETAKE";
        out.reviewRequired = false;
        out.retakeGuidanceKey = nx_guidance(q.failureMode);
        out.grade = NaN;
        out.posterior = NaN;
        out.pReferable = NaN;
        return
    end

    enh = nx_enhance(imgPath);
    s = nx_structures(enh);
    L = nx_lesions(enh, s);
    g = nx_grade(enh, L, q, s);
    criteria = nx_icdr_criteria(L, s);
    evidence = nx_evidence_crops(imgPath, L, criteria, outDir);
    cam = nx_gradcam(enh, g, outDir);

    out.decision = g.decision;
    out.reviewRequired = g.reviewRequired;
    out.retakeGuidanceKey = NaN;
    out.grade = g.grade;
    out.posterior = g.posterior;
    out.pReferable = g.pReferable;
    out.laterality = s.laterality;
    out.criteria = nx_json_array(criteria);
    out.evidence = nx_json_array(evidence);
    out.gradcamPath = cam;
    out.llp = g.lesionLocalisationPrecision;
    out.reportPath = nx_report(out, outDir);
    out.fhirBundle = nx_fhir(out);
end

function qOut = local_quality(q)
    qOut = struct();
    qOut.verdict = q.verdict;
    qOut.score = q.score;
    qOut.failureMode = q.failureMode;
    qOut.phash = q.phash;
end
