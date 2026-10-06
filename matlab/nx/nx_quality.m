function q = nx_quality(imgPath)
%NX_QUALITY  Image-quality gate: Laplacian variance, illumination, FOV, pHash.
%   q = nx_quality(imgPath) returns a contract 6.1 quality struct:
%     .verdict       "accept" | "enhance" | "reject"
%     .score         0–1
%     .failureMode   none | defocus | underexposed | overexposed | partial_fov | media_opacity
%     .phash         16 hex chars
%     .lapVar .illumMean .illumCV .fovArea .fovCircularity  (extra, stripped before JSON)

    arguments
        imgPath (1,1) string {mustBeFile}
    end

    [~, gray, green, fov] = nx_fov(imgPath);
    [h, w] = size(gray);
    [yy, xx] = ndgrid(1:h, 1:w);
    cy = (h + 1) / 2;
    cx = (w + 1) / 2;
    r = hypot(xx - cx, yy - cy);
    arcade = fov & (r < 0.85 * min(h, w) / 2);

    kernel = fspecial("laplacian", 0);
    lap = imfilter(gray, kernel, "replicate");
    if any(arcade, "all")
        lapVar = var(lap(arcade));
        g = green(fov);
        illumMean = mean(g);
        illumCV = std(g) / max(illumMean, eps);
    else
        lapVar = 0;
        illumMean = 0;
        illumCV = 0;
    end

    fovArea = nnz(fov) / numel(fov);
    fovCircularity = local_circularity(fov);

    q = struct();
    q.phash = nx_phash(gray);
    q.lapVar = lapVar;
    q.illumMean = illumMean;
    q.illumCV = illumCV;
    q.fovArea = fovArea;
    q.fovCircularity = fovCircularity;

    % Illumination first: a dark frame also breaks FOV circularity, and the
    % instruction has to be "add light", not "centre the eye".
    if illumMean < 0.12
        q.failureMode = "underexposed";
        q.verdict = "reject";
    elseif illumMean > 0.85
        q.failureMode = "overexposed";
        q.verdict = "reject";
    elseif fovArea < 0.45 || fovCircularity < 0.70
        q.failureMode = "partial_fov";
        q.verdict = "reject";
    elseif lapVar < 5e-4
        q.failureMode = "defocus";
        q.verdict = "reject";
    elseif illumCV > 0.85
        q.failureMode = "media_opacity";
        q.verdict = "reject";
    elseif lapVar < 1.5e-3 || illumMean < 0.18
        q.failureMode = "none";
        q.verdict = "enhance";
    else
        q.failureMode = "none";
        q.verdict = "accept";
    end

    focusScore = min(1, lapVar / 0.003);
    illumScore = 1 - min(1, abs(illumMean - 0.30) / 0.30);
    fovScore = min(1, fovArea / 0.66);
    q.score = max(0, min(1, 0.5 * focusScore + 0.25 * illumScore + 0.25 * fovScore));
    if q.verdict == "reject"
        q.score = min(q.score, 0.35);
    end
end

function c = local_circularity(fov)
    stats = regionprops(fov, "Area", "Perimeter");
    if isempty(stats)
        c = 0;
        return
    end
    [~, idx] = max([stats.Area]);
    perim = stats(idx).Perimeter;
    if perim <= 0
        c = 0;
        return
    end
    c = 4 * pi * stats(idx).Area / (perim ^ 2);
    c = min(c, 1);
end
