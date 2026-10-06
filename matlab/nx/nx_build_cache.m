function nx_build_cache(imgDir, cacheDir)
%NX_BUILD_CACHE  Precompute enhanced images for training (preprocessing versioned folder).
%   Does not read licensed datasets unless the human has placed them under imgDir.

    arguments
        imgDir (1,1) string
        cacheDir (1,1) string
    end

    if ~isfolder(imgDir)
        error("nx:cache:missingInput", "Image folder %s is not present", imgDir);
    end
    if ~isfolder(cacheDir)
        mkdir(cacheDir);
    end
    files = dir(fullfile(imgDir, "*.png"));
    files = [files; dir(fullfile(imgDir, "*.jpg"))];
    files = [files; dir(fullfile(imgDir, "*.jpeg"))];
    for k = 1:numel(files)
        src = fullfile(files(k).folder, files(k).name);
        enh = nx_enhance(src);
        [~, stem] = fileparts(files(k).name);
        imwrite(enh.rgb, fullfile(cacheDir, stem + ".png"));
    end
end
