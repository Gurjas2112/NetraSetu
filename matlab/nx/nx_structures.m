function s = nx_structures(enh)
%NX_STRUCTURES  Optic disc, fovea and vessel mask on the enhanced crop.
%   Coordinates are in the enhanced image. Disc diameter is in those pixels.

    arguments
        enh (1,1) struct
    end

    rgb = enh.rgb;
    I = im2double(rgb);
    green = I(:, :, 2);
    gray = rgb2gray(I);
    [h, w] = size(gray);

    s = struct();
    s.discCenter = [NaN NaN];
    s.discRadius = NaN;
    s.fovea = [NaN NaN];
    s.laterality = "unknown";
    s.vessels = false(h, w);

    rMin = max(8, round(min(h, w) * 0.03));
    rMax = max(rMin + 2, round(min(h, w) * 0.12));
    [centers, radii] = imfindcircles(green, [rMin rMax], ...
        "ObjectPolarity", "bright", "Sensitivity", 0.92);
    if isempty(centers)
        % Brightest large blob as a fallback disc.
        bw = imbinarize(imgaussfilt(green, 3), "adaptive");
        bw = bwareaopen(bw, round(pi * rMin^2));
        st = regionprops(bw, green, "WeightedCentroid", "EquivDiameter");
        if ~isempty(st)
            [~, idx] = max([st.EquivDiameter]);
            centers = st(idx).WeightedCentroid;
            radii = st(idx).EquivDiameter / 2;
        end
    end
    if ~isempty(centers)
        s.discCenter = centers(1, :);
        s.discRadius = radii(1);
    end

    dark = imgaussfilt(1 - gray, 8);
    if all(isfinite(s.discCenter))
        [yy, xx] = ndgrid(1:h, 1:w);
        distDisc = hypot(xx - s.discCenter(1), yy - s.discCenter(2));
        macula = distDisc > 1.5 * s.discRadius & distDisc < 5 * s.discRadius;
        dark(~macula) = 0;
    end
    [~, idx] = max(dark(:));
    [fy, fx] = ind2sub([h w], idx);
    s.fovea = [fx fy];

    if all(isfinite(s.discCenter)) && all(isfinite(s.fovea))
        if s.discCenter(1) > s.fovea(1)
            s.laterality = "OD";
        else
            s.laterality = "OS";
        end
    end

    % Vessel extraction: black top-hat with rotating linear elements.
    inv = imcomplement(green);
    acc = zeros(h, w);
    len = max(9, round(min(h, w) * 0.04));
    for ang = 0:15:165
        acc = max(acc, imtophat(inv, strel("line", len, ang)));
    end
    v = acc > 1.5 * graythresh(acc);
    v = bwareaopen(v, 30);
    if all(isfinite(s.discRadius))
        [yy, xx] = ndgrid(1:h, 1:w);
        disc = hypot(xx - s.discCenter(1), yy - s.discCenter(2)) < 0.6 * s.discRadius;
        v(disc) = false;
    end
    s.vessels = v;
end
