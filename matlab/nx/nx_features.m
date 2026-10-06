function f = nx_features(L, s, q)
%NX_FEATURES  Stream B (~24 ICDR-aligned lesion features) plus Stream C quality.

    arguments
        L (1,1) struct
        s (1,1) struct
        q (1,1) struct
    end

    ma = local_n(L, "MA");
    he = local_n(L, "HE");
    ex = local_n(L, "EX");
    se = local_n(L, "SE");
    nv = local_n(L, "NV_PROXY");

    heQ = local_quadrants(L, "HE");
    maQ = local_quadrants(L, "MA");
    exQ = local_quadrants(L, "EX");
    minExDD = local_min_dd(L, "EX");
    minHeDD = local_min_dd(L, "HE");

    vesselFrac = 0;
    if isfield(s, "vessels") && ~isempty(s.vessels)
        vesselFrac = nnz(s.vessels) / numel(s.vessels);
    end
    discR = 0;
    if isfinite(s.discRadius)
        discR = s.discRadius;
    end

    f = zeros(1, 24);
    f(1) = ma;
    f(2) = he;
    f(3) = ex;
    f(4) = se;
    f(5) = nv;
    f(6) = heQ;
    f(7) = maQ;
    f(8) = exQ;
    f(9) = double(heQ >= 2);
    f(10) = double(heQ >= 4);
    f(11) = double(nv > 0);
    f(12) = minExDD;
    f(13) = minHeDD;
    f(14) = double(minExDD < 1);
    f(15) = vesselFrac;
    f(16) = discR;
    f(17) = q.score;
    f(18) = q.lapVar;
    f(19) = q.illumMean;
    f(20) = q.illumCV;
    f(21) = q.fovArea;
    f(22) = q.fovCircularity;
    f(23) = ma + he;
    f(24) = log1p(he);
    f(~isfinite(f)) = 0;
end

function n = local_n(L, name)
    if ~isfield(L, name) || isempty(L.(name))
        n = 0;
    else
        n = numel(L.(name));
    end
end

function nq = local_quadrants(L, name)
    if ~isfield(L, name) || isempty(L.(name))
        nq = 0;
        return
    end
    nq = numel(unique(string({L.(name).quadrant})));
end

function d = local_min_dd(L, name)
    d = 99;
    if ~isfield(L, name) || isempty(L.(name))
        return
    end
    vals = [L.(name).distanceToFoveaDD];
    vals = vals(isfinite(vals));
    if ~isempty(vals)
        d = min(vals);
    end
end
