function enh = nx_enhance(imgPath)
%NX_ENHANCE  FOV crop, Ben Graham normalisation, CLAHE on L*.
%   enh.rgb is uint8 on the cropped canvas. enh.origin is [x y] of that canvas
%   in the original image (1-based). enh.scale is crop-pixels / original-pixels
%   along each axis (1 after a crop without resize).

    arguments
        imgPath (1,1) string {mustBeFile}
    end

    [rgb, ~, ~, fov] = nx_fov(imgPath);
    stats = regionprops(fov, "BoundingBox");
    if isempty(stats)
        crop = rgb;
        origin = [1 1];
    else
        box = stats(1).BoundingBox; % [x y w h] in spatial coords
        x1 = max(1, floor(box(1)));
        y1 = max(1, floor(box(2)));
        x2 = min(size(rgb, 2), ceil(box(1) + box(3) - 1));
        y2 = min(size(rgb, 1), ceil(box(2) + box(4) - 1));
        crop = rgb(y1:y2, x1:x2, :);
        origin = [x1 y1];
    end

    I = im2double(crop);
    % Ben Graham: subtract a wide Gaussian so illumination is locally flattened.
    sigma = max(size(I, 1), size(I, 2)) * 0.05;
    bg = imgaussfilt(I, sigma);
    flat = I - bg + 0.5;
    lab = rgb2lab(max(0, min(1, flat)));
    L = lab(:, :, 1) / 100;
    L = adapthisteq(L, "NumTiles", [8 8], "ClipLimit", 0.01);
    lab(:, :, 1) = L * 100;
    out = lab2rgb(lab);

    enh = struct();
    enh.rgb = im2uint8(max(0, min(1, out)));
    enh.origin = origin;
    enh.scale = 1;
    enh.size = [size(enh.rgb, 2), size(enh.rgb, 1)];
end
