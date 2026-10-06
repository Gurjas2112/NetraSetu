function g = nx_grade(enh, L, q, s)
%NX_GRADE  Two-stream fusion + quality, temperature-scaled posterior, ICDR decision.
%   Stream A is the ordinal CNN when a model file exists. Stream B is nx_features.
%   Stream C is quality. Without a trained fusion model the posterior comes from
%   the ICDR feature rules — not from a claimed accuracy number.
%
%   A placeholder threshold.json never yields ROUTINE: the patient is referred
%   until eval/run_validation.m freezes an operating point.

    arguments
        enh (1,1) struct
        L (1,1) struct
        q (1,1) struct
        s (1,1) struct
    end

    cfg = nx_config();
    mdl = nx_model();
    feats = nx_features(L, s, q);

    streamA = nan(1, 5);
    if ~isempty(mdl.ordinalNet)
        img = imresize(im2double(enh.rgb), cfg.inputSize);
        try
            raw = predict(mdl.ordinalNet, img);
            streamA = local_from_score(raw);
        catch
            streamA = nan(1, 5);
        end
    end

    streamB = local_icdr_posterior(L);

    if ~isempty(mdl.fusion)
        try
            [~, score] = predict(mdl.fusion, feats);
            logits = log(max(score, eps));
        catch
            logits = log(max(streamB, eps));
        end
    else
        logits = log(max(streamB, eps));
        if all(isfinite(streamA))
            logits = logits + log(max(streamA, eps));
        end
        logits = logits + 0.1 * [q.score, q.score, 0, 0, 0];
    end

    T = max(mdl.temperature, eps);
    posterior = local_softmax(logits / T);
    [pMax, idx] = max(posterior);
    grade = idx - 1;
    pReferable = posterior(3) + posterior(4) + posterior(5);

    g = struct();
    g.posterior = posterior;
    g.grade = grade;
    g.pReferable = pReferable;
    g.confidence = pMax;
    g.features = feats;
    g.lesionLocalisationPrecision = NaN;

    highConf = pMax >= 0.80;
    if ~isfinite(cfg.threshold)
        % No frozen operating point yet: never auto-discharge.
        g.decision = "REFER";
        g.reviewRequired = true;
    elseif pReferable >= cfg.threshold
        g.decision = "REFER";
        g.reviewRequired = true;
    elseif grade <= 1 && highConf
        g.decision = "ROUTINE";
        g.reviewRequired = false;
    else
        g.decision = "REFER";
        g.reviewRequired = true;
    end
end

function p = local_icdr_posterior(L)
    nMA = local_count(L, "MA");
    nHE = local_count(L, "HE");
    nEX = local_count(L, "EX");
    nNV = local_count(L, "NV_PROXY");
    heQ = 0;
    if isfield(L, "HE") && ~isempty(L.HE)
        heQ = numel(unique(string({L.HE.quadrant})));
    end
    if nNV > 0
        p = [0.01 0.02 0.07 0.20 0.70];
    elseif heQ >= 4
        p = [0.02 0.05 0.18 0.60 0.15];
    elseif heQ >= 2 || nHE >= 5
        p = [0.02 0.07 0.61 0.24 0.06];
    elseif nMA >= 1 || nEX >= 1
        p = [0.15 0.60 0.18 0.05 0.02];
    else
        p = [0.90 0.07 0.02 0.007 0.003];
    end
    p = p / sum(p);
end

function n = local_count(L, name)
    if ~isfield(L, name) || isempty(L.(name))
        n = 0;
    else
        n = numel(L.(name));
    end
end

function p = local_from_score(raw)
    raw = double(raw(:))';
    if numel(raw) == 1
        % Ordinal score 0–4 → five bins via a triangular kernel.
        x = 0:4;
        p = exp(-((x - raw) .^ 2) / (2 * 0.45^2));
    else
        p = raw(1:min(5, numel(raw)));
        if numel(p) < 5
            p(end+1:5) = 0; %#ok<AGROW>
        end
    end
    p = p / sum(p);
end

function p = local_softmax(z)
    z = z - max(z);
    e = exp(z);
    p = e / sum(e);
end
