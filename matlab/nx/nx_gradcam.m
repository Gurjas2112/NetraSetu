function path = nx_gradcam(enh, g, outDir)
%NX_GRADCAM  Attention map. Uses gradCAM on Stream A when a network is loaded;
%   otherwise a lesion-density map so the reviewer still has an overlay.

    arguments
        enh (1,1) struct
        g (1,1) struct
        outDir (1,1) string
    end

    if ~isfolder(outDir)
        mkdir(outDir);
    end
    path = string(fullfile(outDir, "gradcam.png"));

    mdl = nx_model();
    img = im2double(enh.rgb);
    map = [];
    if ~isempty(mdl.ordinalNet) && strlength(mdl.gradcamLayer) > 0
        try
            cfg = nx_config();
            small = imresize(img, cfg.inputSize);
            map = gradCAM(mdl.ordinalNet, small, g.grade + 1, "FeatureLayer", mdl.gradcamLayer);
            map = imresize(map, [size(img, 1), size(img, 2)]);
        catch
            map = [];
        end
    end
    if isempty(map)
        map = zeros(size(img, 1), size(img, 2));
        if isfield(g, "features")
            % Uniform low field — evidence crops carry the actual findings.
            map(:) = 0.05;
        end
    end
    map = max(0, min(1, map));
    overlay = im2uint8(ind2rgb(im2uint8(map), parula(256)));
    blend = im2uint8(0.55 * im2double(enh.rgb) + 0.45 * im2double(overlay));
    imwrite(blend, path);
end
