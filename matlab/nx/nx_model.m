function m = nx_model(options)
%NX_MODEL  Persistent load of Stream A, fusion ensemble, MA CNN and temperature.
%   Missing files are allowed: grading then uses the ICDR feature fallback.

    arguments
        options.Reload (1,1) logical = false
    end

    persistent cached
    if ~isempty(cached) && ~options.Reload
        m = cached;
        return
    end

    cfg = nx_config();
    m = struct();
    m.ordinalNet = [];
    m.fusion = [];
    m.maCnn = [];
    m.temperature = 1;
    m.gradcamLayer = "";
    m.loaded = false;

    if isfile(cfg.modelFile)
        S = load(cfg.modelFile);
        if isfield(S, "ordinalNet")
            m.ordinalNet = S.ordinalNet;
        end
        if isfield(S, "fusion")
            m.fusion = S.fusion;
        end
        if isfield(S, "maCnn")
            m.maCnn = S.maCnn;
        end
        if isfield(S, "temperature") && isnumeric(S.temperature)
            m.temperature = double(S.temperature);
        end
        if isfield(S, "gradcamLayer")
            m.gradcamLayer = string(S.gradcamLayer);
        end
        m.loaded = true;
    end
    cached = m;
end
