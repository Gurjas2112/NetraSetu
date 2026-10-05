function v = nx_version()
%NX_VERSION  Version information for the pipeline, safe for jsonencode.

    cfg = nx_config();
    v = struct();
    v.contractVersion = cfg.contractVersion;
    v.modelVer = cfg.modelVer;
    v.cfgHash = cfg.cfgHash;
    v.matlabRelease = string(version("-release"));
end
