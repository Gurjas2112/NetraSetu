function out = erlang_check(lambda, mu, c)
%ERLANG_CHECK  Analytic M/M/c (Erlang C) wait for the grader Resource Pool.
%
%   out = erlang_check(lambda, mu, c) uses consistent rate units (e.g. per hour).
%   lambda — arrivals to the review pool; mu — service rate per grader;
%   c — number of graders (servers).
%
%   Returns struct fields: stable, rho, offeredLoad, P0, Pw, Wq, W (all times
%   in the same unit as 1/mu and 1/lambda).

arguments
    lambda (1,1) double {mustBeNonnegative}
    mu (1,1) double {mustBePositive}
    c (1,1) {mustBeInteger, mustBePositive}
end

a = lambda / mu;
rho = lambda / (c * mu);

out = struct();
out.offeredLoad = a;
out.rho = rho;
out.stable = rho < 1;

if ~out.stable
    out.P0 = NaN;
    out.Pw = NaN;
    out.Wq = Inf;
    out.W = Inf;
    return;
end

sum0 = 0.0;
for n = 0:c - 1
    sum0 = sum0 + a^n / factorial(n);
end

ecTerm = (a^c / factorial(c)) / (1 - rho);
out.P0 = 1 / (sum0 + ecTerm);
out.Pw = ecTerm * out.P0;
out.Wq = out.Pw / (c * mu - lambda);
out.W = out.Wq + 1 / mu;
end
