function evidence = nx_evidence_crops(imgPath, L, criteria, outDir)
%NX_EVIDENCE_CROPS  200×200 native-resolution crops around each lesion centroid.

    arguments
        imgPath (1,1) string {mustBeFile}
        L (1,1) struct
        criteria struct
        outDir (1,1) string
    end

    evDir = fullfile(outDir, "ev");
    if ~isfolder(evDir)
        mkdir(evDir);
    end

    orig = imread(imgPath);
    [h, w, ~] = size(orig);
    types = ["MA", "HE", "EX", "SE", "NV_PROXY"];
    evidence = struct("type", {}, "x", {}, "y", {}, "quadrant", {}, ...
        "distanceToFoveaDD", {}, "cropPath", {}, "criterionKey", {});
    n = 0;
    for t = types
        if ~isfield(L, t) || isempty(L.(t))
            continue
        end
        items = L.(t);
        for k = 1:numel(items)
            n = n + 1;
            x = items(k).x;
            y = items(k).y;
            x1 = max(1, round(x) - 99);
            y1 = max(1, round(y) - 99);
            x2 = min(w, x1 + 199);
            y2 = min(h, y1 + 199);
            x1 = max(1, x2 - 199);
            y1 = max(1, y2 - 199);
            crop = orig(y1:y2, x1:x2, :);
            if size(crop, 1) < 200 || size(crop, 2) < 200
                pad = zeros(200, 200, 3, "uint8");
                pad(1:size(crop, 1), 1:size(crop, 2), :) = crop;
                crop = pad;
            end
            fname = sprintf("%02d.png", n);
            fpath = fullfile(evDir, fname);
            imwrite(crop, fpath);
            key = local_criterion(items(k), criteria);
            dd = items(k).distanceToFoveaDD;
            if ~isfinite(dd)
                dd = NaN;
            end
            evidence(n).type = char(t); %#ok<AGROW>
            evidence(n).x = x;
            evidence(n).y = y;
            evidence(n).quadrant = char(items(k).quadrant);
            evidence(n).distanceToFoveaDD = dd;
            evidence(n).cropPath = char(fpath);
            if isempty(key)
                key = NaN;
            end
            evidence(n).criterionKey = key;
        end
    end
end

function key = local_criterion(item, criteria)
    key = [];
    if isempty(criteria)
        return
    end
    typ = string(item.type);
    for k = 1:numel(criteria)
        ckey = string(criteria(k).key);
        if typ == "HE" && contains(ckey, "haem")
            key = char(ckey);
            return
        end
        if typ == "NV_PROXY" && contains(ckey, "nv")
            key = char(ckey);
            return
        end
        if typ == "EX" && contains(ckey, "exud")
            key = char(ckey);
            return
        end
        if typ == "MA" && (contains(ckey, "micro") || contains(ckey, ".ma"))
            key = char(ckey);
            return
        end
    end
end
