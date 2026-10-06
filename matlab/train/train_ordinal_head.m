function train_ordinal_head()
%TRAIN_ORDINAL_HEAD  Stream A ordinal regression, 512 px, MiniBatchSize 16, CheckpointPath set.
%   Expects local images under data/aptos/train_cache (run nx_build_cache first) and
%   data/splits.json. Does not download datasets.

    repo = fileparts(fileparts(fileparts(mfilename("fullpath"))));
    cacheDir = fullfile(repo, "data", "aptos", "train_cache");
    splitPath = fullfile(repo, "data", "splits.json");
    if ~isfolder(cacheDir) || ~isfile(splitPath)
        fprintf("Skip: need %s and %s (datasets are local, never committed).\n", cacheDir, splitPath);
        return
    end

    cfg = nx_config();
    if canUseGPU()
        reset(gpuDevice);
    end

    net = imagePretrainedNetwork("efficientnetb0", NumClasses=1);
    % Replace the classification head with a single regression output when the
    % network still has a softmax. TODO(verify) layer names on the installed release.
    opts = trainingOptions("adam", ...
        MiniBatchSize=16, ...
        MaxEpochs=30, ...
        InitialLearnRate=1e-4, ...
        ExecutionEnvironment="gpu", ...
        Shuffle="every-epoch", ...
        CheckpointPath=fullfile(repo, "matlab", "models", "checkpoints"), ...
        Plots="none", ...
        Verbose=true);

    ds = imageDatastore(cacheDir);
    if ~isfolder(opts.CheckpointPath)
        mkdir(opts.CheckpointPath);
    end
    net = trainnet(ds, net, "mse", opts);

    outFile = cfg.modelFile;
    if ~isfolder(fileparts(outFile))
        mkdir(fileparts(outFile));
    end
    ordinalNet = net;
    if isfile(outFile)
        save(outFile, "ordinalNet", "-append");
    else
        save(outFile, "ordinalNet");
    end
end
