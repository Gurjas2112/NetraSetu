function train_calibrate()
%TRAIN_CALIBRATE  Fit a temperature scalar on the validation split. Writes into the model file.

    repo = fileparts(fileparts(fileparts(mfilename("fullpath"))));
    logitsFile = fullfile(repo, "matlab", "models", "val_logits.mat");
    if ~isfile(logitsFile)
        fprintf("Skip: %s is not present. Run validation inference first.\n", logitsFile);
        return
    end
    S = load(logitsFile);
    % One-parameter temperature: minimise NLL on validation logits/labels.
    nll = @(T) local_nll(S.logits, S.labels, T);
    temperature = fminbnd(nll, 0.05, 5);
    cfg = nx_config();
    if isfile(cfg.modelFile)
        save(cfg.modelFile, "temperature", "-append");
    else
        save(cfg.modelFile, "temperature");
    end
end

function v = local_nll(logits, labels, T)
    z = logits / T;
    z = z - max(z, [], 2);
    e = exp(z);
    p = e ./ sum(e, 2);
    idx = sub2ind(size(p), (1:size(p, 1))', labels(:) + 1);
    v = -mean(log(max(p(idx), eps)));
end
