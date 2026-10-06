function cfg = nx_config(options)
%NX_CONFIG  Pipeline configuration, cached for the life of the MATLAB session.
%   cfg = nx_config() returns the cached configuration.
%   cfg = nx_config(Reload=true) re-reads threshold.json and recomputes its hash.
%
%   cfg.cfgHash is "sha256:<hex>" of the raw bytes of matlab/config/threshold.json, the same
%   value eval/check_threshold_hash.py computes.

    arguments
        options.Reload (1,1) logical = false
    end

    persistent cached
    if ~isempty(cached) && ~options.Reload
        cfg = cached;
        return
    end

    matlabRoot = fileparts(fileparts(mfilename("fullpath")));
    thresholdPath = fullfile(matlabRoot, "config", "threshold.json");

    fid = fopen(thresholdPath, "r");
    if fid < 0
        error("nx:config:missingThreshold", "Cannot open %s", thresholdPath);
    end
    closer = onCleanup(@() fclose(fid));
    bytes = fread(fid, Inf, "*uint8")';
    clear closer

    thresholdCfg = jsondecode(char(bytes));

    cfg = struct();
    cfg.contractVersion = "1.1";
    cfg.modelVer = "netrasetu_v1";
    cfg.matlabRoot = string(matlabRoot);
    cfg.thresholdPath = string(thresholdPath);
    cfg.cfgHash = "sha256:" + local_sha256_hex(bytes);
    cfg.thresholdIsPlaceholder = isfield(thresholdCfg, "placeholder") && thresholdCfg.placeholder;
    if isfield(thresholdCfg, "threshold") && isnumeric(thresholdCfg.threshold) ...
            && isscalar(thresholdCfg.threshold)
        cfg.threshold = double(thresholdCfg.threshold);
    else
        cfg.threshold = NaN;
    end

    cached = cfg;
end

function hex = local_sha256_hex(bytes)
    md = java.security.MessageDigest.getInstance("SHA-256");
    md.update(typecast(uint8(bytes), "int8"));
    digest = typecast(md.digest(), "uint8");
    hex = string(lower(reshape(dec2hex(digest, 2)', 1, [])));
end
