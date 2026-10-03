
# MandatePool

A shared GEN pool on GenLayer. Members deposit and receive shares. An agent proposes a buy or a sell against a mandate written at deploy. Validators read the cited public pages and return approve, reject, or abstain. A buy pays the named counterparty only after approve. The contract does not place an exchange order. Sale proceeds come back only when someone sends GEN to repay.

## Pool

Deposits mint shares. The first deposit is one share per wei. Later deposits mint at the current cash-per-share price. Cash is the GEN held by the contract, including amounts reserved for approved buys that have not executed.

A withdrawal burns shares and pays that fraction of cash, but only from free cash. Free cash is cash minus reserved. A withdrawal that would touch a reserved buy reverts.

## Mandate

The mandate is fixed at deploy. A proposal must name one asset, say buy or sell, and cite one to five public https sources. Validators judge whether the proposal is inside that mandate and supported by those pages. They do not judge whether it will make money.

approve reserves the buy amount until execute or expiry. reject and abstain leave the pool untouched. A source that cannot be fetched reverts, so the proposal can be reviewed again.

## Execution

An approved buy can be executed before expiry. The position cap is max_position_bps of pool cash. The protocol fee is taken from the buy and sent to the treasury. The rest is paid to the counterparty named in the proposal. Reserved funds are released and cash falls by the full amount.

An approved sell records the instruction. It does not send GEN.

Anyone can call repay with a value after execution. That GEN is the proceeds, and it increases cash.

report reads one evidence URL and returns met, missed, or unclear. The agent fee is paid to the proposer only on met, and only from free cash.

An approved proposal that is not executed can be released after expiry. A buy reservation returns to free cash.

## Contract

contracts/mandate_pool.py, Studionet runner.

# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

### Constructor

MandatePool(treasury, mandate, max_position_bps, agent_fee_bps, protocol_fee_bps)

- mandate: 40 to 4000 characters
- max_position_bps: 1 to 2500
- agent_fee_bps: 0 to 500
- protocol_fee_bps: 0 to 200

A 10% cap, a 0.5% agent fee, and a 0.2% protocol fee are 1000, 50, and 20.

### Writes

| Method | Who | What |
| --- | --- | --- |
| deposit | payable | Mint shares for the sent GEN |
| withdraw(share_amount) | a member | Burn shares and take free cash |
| propose(...) | anyone | Open a buy or sell |
| review(pid) | anyone | Approve, reject, or abstain from the sources |
| execute(pid) | anyone | Pay an approved buy, or record an approved sell |
| repay(pid) | payable | Return proceeds to the pool |
| report(pid, evidence_url) | anyone | met, missed, or unclear; met pays the agent |
| release_expired(pid) | anyone | Free an unexecuted approval after expiry |

propose takes asset, action, amount, thesis, sources_json, counterparty, and expiry_minutes. sources_json is a JSON array of https URLs. expiry_minutes is 60 to 43200. A sell may pass an empty counterparty.

### Views

get_config, get_shares(holder), get_proposal(pid), get_proposals(start, limit).

Status moves pending to approved, rejected, executed, reported, or expired.

## Tests

Direct mode, with web and LLM mocked. From the repo root:

python -m pytest tests/direct/test_mandate_pool.py -v
