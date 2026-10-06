function path = nx_report(out, outDir)
%NX_REPORT  One-page screening report via MATLAB Report Generator, if installed.

    arguments
        out (1,1) struct
        outDir (1,1) string
    end

    path = NaN;
    if exist("mlreportgen.report.Report", "class") ~= 8
        return
    end
    if ~isfolder(outDir)
        mkdir(outDir);
    end
    path = string(fullfile(outDir, "report.pdf"));
    import mlreportgen.report.* %#ok<SIMPT>
    import mlreportgen.dom.* %#ok<SIMPT>
    rpt = Report(char(path), "pdf");
    try
        title = Text("NetraSetu screening report");
        title.Bold = true;
        add(rpt, title);
        add(rpt, Paragraph("Decision: " + string(out.decision)));
        if isfield(out, "grade") && isnumeric(out.grade) && isfinite(out.grade)
            add(rpt, Paragraph("Grade: " + string(out.grade)));
        end
        add(rpt, Paragraph("Model: " + string(out.modelVer)));
        close(rpt);
    catch
        try, close(rpt); catch, end %#ok<CTCH>
        path = NaN;
    end
end
