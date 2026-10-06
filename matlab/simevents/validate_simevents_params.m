function validate_simevents_params(params)
%VALIDATE_SIMEVENTS_PARAMS  Required fields before building the District Twin.
arguments
    params (1,1) struct
end

required = { ...
    "inferenceServiceTimeSeconds", "p95", @isnumeric; ...
    "graderCount", "", @(x) isnumeric(x) && x >= 1; ...
    "arrivalsPerDay", "", @(x) isnumeric(x) && x > 0; ...
    "reworkRate", "", @(x) isnumeric(x) && x >= 0 && x < 1; ...
    "cacheHitRate", "", @(x) isnumeric(x) && x >= 0 && x < 1; ...
    "referToReviewFraction", "", @(x) isnumeric(x) && x >= 0 && x <= 1; ...
    "uploadMegabytes", "", @(x) isnumeric(x) && x > 0; ...
    "uplinkMbps", "", @(x) isnumeric(x) && x > 0 ...
    };

for i = 1:size(required, 1)
    top = required{i, 1};
    sub = required{i, 2};
    pred = required{i, 3};
    if sub == ""
        value = params.(top);
    else
        if ~isfield(params, top) || ~isfield(params.(top), sub)
            value = [];
        else
            value = params.(top).(sub);
        end
    end
    if isempty(value) || ~pred(value)
        if sub == ""
            label = top;
        else
            label = top + "." + sub;
        end
        error("validate_simevents_params:Missing", ...
            "params.json field %s must be set before build_district_twin (measured, not guessed).", label);
    end
end
end
