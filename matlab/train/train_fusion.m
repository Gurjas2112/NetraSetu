function train_fusion()
%TRAIN_FUSION  fitcensemble on Stream B (+ C) features. Requires features.mat and labels.

    repo = fileparts(fileparts(fileparts(mfilename("fullpath"))));
    featFile = fullfile(repo, "matlab", "models", "features.mat");
    labelFile = fullfile(repo, "data", "aptos", "labels.mat");
    if ~isfile(featFile) || ~isfile(labelFile)
        fprintf("Skip: %s and %s are required.\n", featFile, labelFile);
        return
    end
    S = load(featFile);
    L = load(labelFile);
    fusion = fitcensemble(S.X, L.y, Method="Bag");
    cfg = nx_config();
    if isfile(cfg.modelFile)
        save(cfg.modelFile, "fusion", "-append");
    else
        save(cfg.modelFile, "fusion");
    end
end
