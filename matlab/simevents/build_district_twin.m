function modelName = build_district_twin(paramsPath)
%BUILD_DISTRICT_TWIN  Programmatic SimEvents model of a district screening programme.
%
%   modelName = build_district_twin() builds netrasetu_district_twin from
%   matlab/simevents/params.json using new_system / add_block / add_line only.
%
%   Topology (Figure 4 in the spec):
%     Poisson arrivals → screening queue → quality gate (rework loop) →
%     transmission delay → cache router → inference server (miss path) →
%     triage router → auto-discharge OR review queue → grader pool (30 s).
%
%   HUMAN-VERIFY: sim(modelName) and compare grader waits with erlang_check.

arguments
    paramsPath (1,1) string = ""
end

params = load_simevents_params(paramsPath);
validate_simevents_params(params);
if isempty(params.inferenceServiceTimeSeconds.p50)
    params.inferenceServiceTimeSeconds.p50 = params.inferenceServiceTimeSeconds.p95;
end
assignin("base", "netrasetu_simevents_params", params);

modelName = "netrasetu_district_twin";
slxPath = fullfile(fileparts(mfilename("fullpath")), modelName + ".slx");

if bdIsLoaded(modelName)
    close_system(modelName, 0);
end
if isfile(slxPath)
    delete(slxPath);
end

new_system(modelName);
open_system(modelName);

stopSeconds = params.simulationDays * 86400;
set_param(modelName, ...
    "StopTime", num2str(stopSeconds), ...
    "SolverType", "Variable-step", ...
    "Solver", "ode23tb", ...
    "FixedStep", "auto");

lib = "simeventslib";
y0 = 40;
dy = 90;
x = 80:200:2680;

add_block([lib "/Entity Generator"], blk(modelName, "Arrivals"), "Position", rect(x(1), y0, 60, 40));
set_param(blk(modelName, "Arrivals"), ...
    "TimeSource", "MATLAB action", ...
    "IntergenerationTimeAction", meanInterarrivalAction(params));

add_block([lib "/Entity Queue"], blk(modelName, "ScreenQueue"), "Position", rect(x(2), y0, 60, 40));

add_block([lib "/Entity Server"], blk(modelName, "QualityGate"), "Position", rect(x(3), y0, 60, 40));
set_param(blk(modelName, "QualityGate"), ...
    "ServiceTimeSource", "MATLAB action", ...
    "ServiceTimeAction", "dt = netrasetu_simevents_params.qualityGateSeconds;", ...
    "ServiceCompleteAction", qualityCompleteAction());

add_block([lib "/Entity Output Switch"], blk(modelName, "QualityRoute"), "Position", rect(x(4), y0, 60, 40));
set_param(blk(modelName, "QualityRoute"), ...
    "ActivePortSource", "From attribute", ...
    "ActivePortAttributeName", "routePort");

add_block([lib "/Entity Server"], blk(modelName, "Transmit"), "Position", rect(x(5), y0, 60, 40));
set_param(blk(modelName, "Transmit"), ...
    "ServiceTimeSource", "MATLAB action", ...
    "ServiceTimeAction", transmitAction(), ...
    "ServiceCompleteAction", cacheRouteAction());

add_block([lib "/Entity Output Switch"], blk(modelName, "CacheRoute"), "Position", rect(x(6), y0, 60, 40));
set_param(blk(modelName, "CacheRoute"), ...
    "ActivePortSource", "From attribute", ...
    "ActivePortAttributeName", "cachePort");

add_block([lib "/Entity Server"], blk(modelName, "Inference"), "Position", rect(x(7), y0 - dy, 60, 40));
set_param(blk(modelName, "Inference"), ...
    "ServiceTimeSource", "MATLAB action", ...
    "ServiceTimeAction", "dt = netrasetu_simevents_params.inferenceServiceTimeSeconds.p95;");

add_block([lib "/Entity Combinator"], blk(modelName, "AfterInference"), "Position", rect(x(8), y0, 60, 40));

add_block([lib "/Entity Server"], blk(modelName, "TriageMark"), "Position", rect(x(9), y0, 60, 40));
set_param(blk(modelName, "TriageMark"), ...
    "ServiceTimeSource", "MATLAB action", ...
    "ServiceTimeAction", "dt = 0.001;", ...
    "ServiceCompleteAction", triageRouteAction());

add_block([lib "/Entity Output Switch"], blk(modelName, "TriageRoute"), "Position", rect(x(10), y0, 60, 40));
set_param(blk(modelName, "TriageRoute"), ...
    "ActivePortSource", "From attribute", ...
    "ActivePortAttributeName", "triagePort");

add_block([lib "/Entity Terminator"], blk(modelName, "RoutineDone"), "Position", rect(x(11), y0 - dy, 60, 40));
add_block([lib "/Entity Queue"], blk(modelName, "ReviewQueue"), "Position", rect(x(11), y0 + dy, 60, 40));

add_block([lib "/Resource Pool"], blk(modelName, "GraderPool"), "Position", rect(x(12), y0 + dy + 60, 40, 40));
set_param(blk(modelName, "GraderPool"), ...
    "ResourceCapacity", num2str(params.graderCount), ...
    "ResourceName", "grader");

add_block([lib "/Resource Acquire"], blk(modelName, "AcquireGrader"), "Position", rect(x(12), y0 + dy, 60, 40));
set_param(blk(modelName, "AcquireGrader"), "ResourceName", "grader");

add_block([lib "/Entity Server"], blk(modelName, "Grader"), "Position", rect(x(13), y0 + dy, 60, 40));
set_param(blk(modelName, "Grader"), ...
    "ServiceTimeSource", "MATLAB action", ...
    "ServiceTimeAction", "dt = netrasetu_simevents_params.graderServiceTimeSeconds;");

add_block([lib "/Resource Release"], blk(modelName, "ReleaseGrader"), "Position", rect(x(14), y0 + dy, 60, 40));
set_param(blk(modelName, "ReleaseGrader"), "ResourceName", "grader");

add_block([lib "/Entity Terminator"], blk(modelName, "ReviewDone"), "Position", rect(x(15), y0 + dy, 60, 40));

wire(modelName, "Arrivals", "ScreenQueue");
wire(modelName, "ScreenQueue", "QualityGate");
wire(modelName, "QualityGate", "QualityRoute");
wireFrom(modelName, "QualityRoute", 1, "Transmit");
wireFrom(modelName, "QualityRoute", 2, "ScreenQueue");
wire(modelName, "Transmit", "CacheRoute");
wireFrom(modelName, "CacheRoute", 1, "AfterInference");
wireFrom(modelName, "CacheRoute", 2, "Inference");
wire(modelName, "Inference", "AfterInference");
wire(modelName, "AfterInference", "TriageMark");
wire(modelName, "TriageMark", "TriageRoute");
wireFrom(modelName, "TriageRoute", 1, "RoutineDone");
wireFrom(modelName, "TriageRoute", 2, "ReviewQueue");
wire(modelName, "ReviewQueue", "AcquireGrader");
wire(modelName, "AcquireGrader", "Grader");
wire(modelName, "Grader", "ReleaseGrader");
wire(modelName, "ReleaseGrader", "ReviewDone");

save_system(modelName, slxPath);
end

function s = blk(model, block)
s = model + "/" + block;
end

function pos = rect(x, y, w, h)
pos = [x, y, x + w, y + h];
end

function wire(model, src, dst)
phS = get_param(blk(model, src), "PortHandles");
phD = get_param(blk(model, dst), "PortHandles");
add_line(model, phS.Outports(1), phD.Inports(1), "autorouting", "on");
end

function wireFrom(model, src, outPort, dst)
phS = get_param(blk(model, src), "PortHandles");
phD = get_param(blk(model, dst), "PortHandles");
add_line(model, phS.Outports(outPort), phD.Inports(1), "autorouting", "on");
end

function txt = meanInterarrivalAction(params)
meanSec = (24 * 3600) / params.arrivalsPerDay;
txt = sprintf("dt = exprnd(%g);", meanSec);
end

function txt = qualityCompleteAction()
txt = sprintf([ ...
    "p = netrasetu_simevents_params;\n" ...
    "if rand() < p.reworkRate\n" ...
    "    entity.routePort = 2;\n" ...
    "else\n" ...
    "    entity.routePort = 1;\n" ...
    "end\n" ...
    ]);
end

function txt = transmitAction()
txt = sprintf([ ...
    "p = netrasetu_simevents_params;\n" ...
    "base = p.uploadMegabytes * 8 / p.uplinkMbps;\n" ...
    "dt = base + exprnd(max(base, 1));\n" ...
    ]);
end

function txt = cacheRouteAction()
txt = sprintf([ ...
    "p = netrasetu_simevents_params;\n" ...
    "if rand() < p.cacheHitRate\n" ...
    "    entity.cachePort = 1;\n" ...
    "else\n" ...
    "    entity.cachePort = 2;\n" ...
    "end\n" ...
    ]);
end

function txt = triageRouteAction()
txt = sprintf([ ...
    "p = netrasetu_simevents_params;\n" ...
    "if rand() < p.referToReviewFraction\n" ...
    "    entity.triagePort = 2;\n" ...
    "else\n" ...
    "    entity.triagePort = 1;\n" ...
    "end\n" ...
    ]);
end
