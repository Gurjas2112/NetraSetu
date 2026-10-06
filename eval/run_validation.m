function run_validation()
%RUN_VALIDATION  Freeze the referral threshold on the validation split, then score the test set.
%   Writes matlab/config/threshold.json and results/validation.json.
%   Does not invent numbers: if splits or predictions are missing it exits without writing metrics.

    repo = fileparts(fileparts(mfilename("fullpath")));
    splitPath = fullfile(repo, "data", "splits.json");
    predFile = fullfile(repo, "results", "predictions.mat");
    outVal = fullfile(repo, "results", "validation.json");
    outThr = fullfile(repo, "matlab", "config", "threshold.json");

    if ~isfile(splitPath) || ~isfile(predFile)
        fprintf("Skip: %s and %s are required. Train and dump predictions on the human machine.\n", ...
            splitPath, predFile);
        return
    end

    pred = load(predFile);
    % pred.yVal, pred.pRefVal, pred.yTest, pred.pRefTest, pred.gradeTest, pred.posteriorTest
    required = ["yVal", "pRefVal", "yTest", "pRefTest"];
    for k = 1:numel(required)
        if ~isfield(pred, required(k))
            error("nx:eval:missingField", "predictions.mat is missing %s", required(k));
        end
    end

    yVal = pred.yVal(:) >= 2;
    pVal = pred.pRefVal(:);
    grid = linspace(0, 1, 1001);
    chosen = NaN;
    for t = grid
        sens = local_sens(yVal, pVal >= t);
        if sens >= 0.90
            chosen = t;
        end
    end
    if ~isfinite(chosen)
        error("nx:eval:noOperatingPoint", "No threshold on validation reached sensitivity 0.90");
    end

    thr = struct();
    thr.placeholder = false;
    thr.threshold = chosen;
    thr.selectedOn = "validation";
    thr.rule = "sensitivity >= 0.90 on the validation split";
    if ~isfolder(fileparts(outThr))
        mkdir(fileparts(outThr));
    end
    local_write_json(outThr, thr);
    nx_config(Reload=true);
    cfg = nx_config();

    yTest = pred.yTest(:) >= 2;
    pTest = pred.pRefTest(:);
    yhat = pTest >= chosen;
    sens = local_sens(yTest, yhat);
    spec = local_spec(yTest, yhat);
    [sensLo, sensHi] = local_boot(yTest, yhat, @local_sens);
    [specLo, specHi] = local_boot(yTest, yhat, @local_spec);

    result = struct();
    result.cfgHash = cfg.cfgHash;
    result.threshold = chosen;
    result.test = struct();
    result.test.sensitivity = struct("value", sens, "ci95", [sensLo, sensHi]);
    result.test.specificity = struct("value", spec, "ci95", [specLo, specHi]);
    result.note = "Filled only by this script from predictions.mat. Do not edit.";
    if ~isfolder(fileparts(outVal))
        mkdir(fileparts(outVal));
    end
    local_write_json(outVal, result);
end

function s = local_sens(y, yhat)
    s = nnz(yhat & y) / max(nnz(y), 1);
end

function s = local_spec(y, yhat)
    s = nnz(~yhat & ~y) / max(nnz(~y), 1);
end

function [lo, hi] = local_boot(y, yhat, fn)
    rng(26038);
    n = numel(y);
    v = zeros(2000, 1);
    for i = 1:2000
        idx = randi(n, n, 1);
        v(i) = fn(y(idx), yhat(idx));
    end
    lo = quantile(v, 0.025);
    hi = quantile(v, 0.975);
end

function local_write_json(path, S)
    txt = jsonencode(S, PrettyPrint=true);
    fid = fopen(path, "w");
    fwrite(fid, txt);
    fclose(fid);
end
