function criteria = nx_icdr_criteria(L, s)
%NX_ICDR_CRITERIA  Match detected lesions to International Clinical DR text keys.

    arguments
        L (1,1) struct
        s (1,1) struct %#ok<INUSA>
    end

    criteria = struct("key", {}, "grade", {}, "detail", {});

    nHE = local_n(L, "HE");
    nMA = local_n(L, "MA");
    nEX = local_n(L, "EX");
    nNV = local_n(L, "NV_PROXY");
    heQ = local_q(L, "HE");

    if nNV > 0
        criteria(end + 1) = local_row("icdr.l4.nv_proxy", 4, struct("proxy", true, "count", nNV)); %#ok<AGROW>
    end
    if heQ >= 4
        criteria(end + 1) = local_row("icdr.l3.haemorrhages_four_quadrants", 3, struct("quadrants", heQ, "count", nHE)); %#ok<AGROW>
    elseif heQ >= 2 || nHE >= 5
        criteria(end + 1) = local_row("icdr.l2.haemorrhages_multi_quadrant", 2, struct("quadrants", heQ, "count", nHE)); %#ok<AGROW>
    end
    if nMA >= 1 && nHE == 0 && nNV == 0
        criteria(end + 1) = local_row("icdr.l1.microaneurysms_only", 1, struct("count", nMA)); %#ok<AGROW>
    end
    if nEX >= 1
        minDD = 99;
        if isfield(L, "EX") && ~isempty(L.EX)
            vals = [L.EX.distanceToFoveaDD];
            vals = vals(isfinite(vals));
            if ~isempty(vals)
                minDD = min(vals);
            end
        end
        criteria(end + 1) = local_row("icdr.exudates.present", 2, struct("count", nEX, "nearestDD", minDD)); %#ok<AGROW>
    end
end

function n = local_n(L, name)
    if ~isfield(L, name) || isempty(L.(name))
        n = 0;
    else
        n = numel(L.(name));
    end
end

function nq = local_q(L, name)
    if ~isfield(L, name) || isempty(L.(name))
        nq = 0;
        return
    end
    nq = numel(unique(string({L.(name).quadrant})));
end

function row = local_row(key, grade, detail)
    row = struct("key", key, "grade", grade, "detail", detail);
end
