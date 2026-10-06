function L = nx_lesions(enh, s)
%NX_LESIONS  Microaneurysm, haemorrhage, exudate and NV-proxy candidates.
%   MA: rotating linear top-hat → optional CNN → 2-D Gaussian sub-pixel fit.
%   NV is a vessel-morphology proxy and is always typed NV_PROXY.

    arguments
        enh (1,1) struct
        s (1,1) struct
    end

    rgb = enh.rgb;
    I = im2double(rgb);
    green = I(:, :, 2);
    [h, w] = size(green);
    inv = imcomplement(green);

    L = struct();
    L.MA = local_empty();
    L.HE = local_empty();
    L.EX = local_empty();
    L.SE = local_empty();
    L.NV_PROXY = local_empty();

    acc = zeros(h, w);
    for ang = 0:15:165
        acc = max(acc, imtophat(inv, strel("line", 9, ang)));
    end
    maMask = acc > 2.5 * graythresh(acc);
    maMask = bwareaopen(maMask, 2);
    maMask = maMask & ~bwareaopen(maMask, 80);
    if ~isempty(s.vessels)
        maMask = maMask & ~imdilate(s.vessels, strel("disk", 1));
    end
    mdl = nx_model();
    if ~isempty(mdl.maCnn)
        maMask = local_ma_cnn(maMask, green, mdl.maCnn);
    end
    L.MA = local_from_mask(maMask, acc, enh, s, "MA");

    blot = (green < 0.18) & (I(:, :, 1) < 0.35);
    blot = bwareaopen(blot, 25);
    blot = blot & ~bwareaopen(blot, 2500);
    if ~isempty(s.vessels)
        blot = blot & ~s.vessels;
    end
    L.HE = local_from_mask(blot, 1 - green, enh, s, "HE");

    yellow = (I(:, :, 1) > 0.70) & (I(:, :, 2) > 0.45) & (I(:, :, 3) < 0.35);
    yellow = bwareaopen(yellow, 8);
    L.EX = local_from_mask(yellow, I(:, :, 1), enh, s, "EX");

    if all(isfinite(s.discCenter)) && isfinite(s.discRadius)
        [yy, xx] = ndgrid(1:h, 1:w);
        ring = hypot(xx - s.discCenter(1), yy - s.discCenter(2));
        nvd = s.vessels & ring > 0.4 * s.discRadius & ring < 1.4 * s.discRadius;
        density = nnz(nvd) / max(nnz(ring < 1.4 * s.discRadius), 1);
        if density > 0.08
            ev = struct("x", s.discCenter(1), "y", s.discCenter(2), ...
                "quadrant", local_quadrant(s.discCenter, s), ...
                "distanceToFoveaDD", local_dd(s.discCenter, s), ...
                "type", "NV_PROXY");
            L.NV_PROXY = ev;
        end
    end
end

function mask = local_ma_cnn(mask, green, net)
% Optional MA CNN: keep a candidate only when the network scores it above 0.5.
    st = regionprops(mask, "PixelIdxList", "BoundingBox");
    keep = false(size(mask));
    for k = 1:numel(st)
        box = st(k).BoundingBox;
        x1 = max(1, floor(box(1)));
        y1 = max(1, floor(box(2)));
        x2 = min(size(green, 2), ceil(box(1) + box(3) - 1));
        y2 = min(size(green, 1), ceil(box(2) + box(4) - 1));
        patch = imresize(green(y1:y2, x1:x2), [32 32]);
        try
            score = predict(net, patch);
            score = double(score);
            score = score(1);
        catch
            keep = mask;
            return
        end
        if score > 0.5
            keep(st(k).PixelIdxList) = true;
        end
    end
    mask = keep;
end

function ev = local_empty()
    ev = struct("x", {}, "y", {}, "quadrant", {}, "distanceToFoveaDD", {}, "type", {});
end

function ev = local_from_mask(mask, weight, enh, s, typ)
    ev = local_empty();
    st = regionprops(mask, weight, "WeightedCentroid", "Area");
    origin = enh.origin;
    for k = 1:numel(st)
        c = st(k).WeightedCentroid;
        c = local_subpixel(weight, c);
        orig = [c(1) + origin(1) - 1, c(2) + origin(2) - 1];
        ev(end + 1) = struct( ... %#ok<AGROW>
            "x", orig(1), "y", orig(2), ...
            "quadrant", local_quadrant(c, s), ...
            "distanceToFoveaDD", local_dd(c, s), ...
            "type", typ);
    end
end

function c = local_subpixel(img, c)
% 2-D Gaussian (actually centroid of a window) for sub-pixel localisation.
    [h, w] = size(img);
    x = round(c(1));
    y = round(c(2));
    x1 = max(1, x - 3);
    x2 = min(w, x + 3);
    y1 = max(1, y - 3);
    y2 = min(h, y + 3);
    patch = double(img(y1:y2, x1:x2));
    patch = max(patch, 0);
    if sum(patch(:)) <= 0
        return
    end
    [xx, yy] = meshgrid(x1:x2, y1:y2);
    c = [sum(xx(:) .* patch(:)) / sum(patch(:)), sum(yy(:) .* patch(:)) / sum(patch(:))];
end

function q = local_quadrant(c, s)
    if ~all(isfinite(s.fovea))
        q = "ST";
        return
    end
    dx = c(1) - s.fovea(1);
    dy = s.fovea(2) - c(2); % image y grows down; superior is smaller y
    if dy >= 0 && dx >= 0
        q = "ST";
    elseif dy >= 0
        q = "SN";
    elseif dx >= 0
        q = "IT";
    else
        q = "IN";
    end
end

function d = local_dd(c, s)
    if ~all(isfinite(s.fovea)) || ~isfinite(s.discRadius) || s.discRadius <= 0
        d = NaN;
        return
    end
    d = hypot(c(1) - s.fovea(1), c(2) - s.fovea(2)) / (2 * s.discRadius);
end
