# Pre-Live Strategy Gate

## Executive summary
No strategy may move to restricted live-candidate status unless every gate in this policy is satisfied with reproducible evidence.

## What was tested
This policy was added as a control document. Gate enforcement is partially represented by existing promotion code and the new scorecard/rejection modules.

## Data used
Repository safety policies, current risk engine behavior, and the research mandate.

## Assumptions
Restricted live-candidate review is not unrestricted live trading. Live activation remains separately gated by env flags, authorization, and operational checklists.

## Methodology
The gate combines research evidence, execution realism, risk compatibility, observability, and operational controls.

## Results
A strategy cannot move to restricted live-candidate status unless all are true: documented hypothesis, reproducible backtest, out-of-sample validation, walk-forward validation, transaction cost model, spread model, slippage model, latency sensitivity, rejected-fill assumptions, regime analysis, risk envelope compatibility, no unresolved data-quality issues, kill switch tested, order sizing tested, max daily loss tested, max open positions tested, cooldown tested, stale-data behavior tested, Telegram alerting tested, dashboard visibility tested, logs capture rationale for every trade decision, strategy can be disabled independently, strategy defaults disabled, live activation requires explicit env flag, live activation requires control-plane authorization, and live activation is documented in an operations checklist.

## What passed
The repo already has fail-closed live env validation, kill switch, risk engine, and protected control-plane patterns.

## What failed
No strategy has completed the evidence package.

## Rejected strategies
All strategies are rejected until they satisfy this gate.

## Strategies needing more paper/shadow validation
All strategies.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
A strategy can satisfy quantitative metrics but still fail operations, observability, or disablement requirements.

## Operational risk notes
Do not weaken this policy to promote a strategy. Do not treat paper profitability as live readiness.

## Next engineering actions
Wire automated gate checks into promotion evaluation after research jobs produce reproducible artifacts.
