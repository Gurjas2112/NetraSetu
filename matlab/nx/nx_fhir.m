function bundle = nx_fhir(out)
%NX_FHIR  FHIR R4 Bundle (collection) with NRCeS-shaped DiagnosticReport and Observation.
%   Not an ABDM submission. The seam exists so a later profile can be swapped in.

    arguments
        out (1,1) struct
    end

    obs = struct();
    obs.resourceType = "Observation";
    obs.status = "final";
    obs.code = struct("text", "ICDR grade");
    if isfield(out, "grade") && isnumeric(out.grade) && isfinite(out.grade)
        obs.valueInteger = out.grade;
    else
        obs.dataAbsentReason = struct("text", "not-graded");
    end

    report = struct();
    report.resourceType = "DiagnosticReport";
    report.status = "final";
    report.code = struct("text", "Diabetic retinopathy screening");
    report.conclusion = char(string(out.decision));

    e1 = struct("resource", report);
    e2 = struct("resource", obs);

    bundle = struct();
    bundle.resourceType = "Bundle";
    bundle.type = "collection";
    bundle.entry = {e1, e2};
end
