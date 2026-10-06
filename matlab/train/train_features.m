function train_features()
%TRAIN_FEATURES  Cache Stream B lesion features for each split image.

    repo = fileparts(fileparts(fileparts(mfilename("fullpath"))));
    imgDir = fullfile(repo, "data", "aptos", "train_cache");
    outFile = fullfile(repo, "matlab", "models", "features.mat");
    if ~isfolder(imgDir)
        fprintf("Skip: %s is not present.\n", imgDir);
        return
    end
    files = dir(fullfile(imgDir, "*.png"));
    X = [];
    names = strings(0, 1);
    for k = 1:numel(files)
        p = fullfile(files(k).folder, files(k).name);
        q = nx_quality(p);
        if q.verdict == "reject"
            continue
        end
        enh = nx_enhance(p);
        s = nx_structures(enh);
        L = nx_lesions(enh, s);
        X = [X; nx_features(L, s, q)]; %#ok<AGROW>
        names(end + 1, 1) = string(files(k).name); %#ok<AGROW>
    end
    if ~isfolder(fileparts(outFile))
        mkdir(fileparts(outFile));
    end
    save(outFile, "X", "names");
end
