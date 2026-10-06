function c = nx_json_array(s)
%NX_JSON_ARRAY  Cell array so jsonencode always emits a JSON array, even for 0 or 1 items.

    arguments
        s struct
    end

    if isempty(s)
        c = {};
    else
        c = num2cell(s);
    end
end
