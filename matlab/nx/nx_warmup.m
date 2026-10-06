function nx_warmup()
%NX_WARMUP  Load config and models so the first screening is not the slow one.

    nx_config();
    nx_model();
    if canUseGPU()
        gpuDevice();
    end
end
