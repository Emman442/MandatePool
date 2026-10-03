"""Direct-mode tests for MandatePool. Web and LLM are mocked."""

import json

CONTRACT = "contracts/mandate_pool.py"
ONE_GEN = 10**18
SOURCE = "https://data.example/btc"
COUNTERPARTY = "0x1111111111111111111111111111111111111111"
MANDATE = (
    "The pool may allocate to publicly listed crypto assets only. "
    "A proposal must name one asset and cite a public https source."
)
THESIS = "Buy bitcoin because the cited public page names bitcoin as the asset."


def deploy(direct_vm, direct_deploy, admin):
    direct_vm.sender = admin
    direct_vm.value = 0
    return direct_deploy(CONTRACT, COUNTERPARTY, MANDATE, 1000, 50, 20)


def deposit(contract, direct_vm, amount_gen):
    direct_vm.value = amount_gen * ONE_GEN
    return contract.deposit()


def sources():
    return json.dumps([SOURCE])


def mock_review(direct_vm, verdict):
    direct_vm.mock_web(r"data\.example/btc", {"status": 200, "body": "Bitcoin is a publicly listed crypto asset."})
    direct_vm.mock_llm(r"investment-mandate checker", verdict)


def open_buy(contract, direct_vm, amount_wei=ONE_GEN):
    direct_vm.value = 0
    return contract.propose("bitcoin", "buy", amount_wei, THESIS, sources(), COUNTERPARTY, 120)


def test_config_and_deposit(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    config = contract.get_config()
    assert config["max_position_bps"] == 1000
    assert config["cash"] == 0
    assert config["total_shares"] == 0

    minted = deposit(contract, direct_vm, 10)
    assert int(minted) == 10 * ONE_GEN
    config = contract.get_config()
    assert config["cash"] == 10 * ONE_GEN
    assert config["free"] == 10 * ONE_GEN
    assert contract.get_shares(config["owner"]) == 10 * ONE_GEN


def test_withdraw_pays_free_cash(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    direct_vm.value = 0
    contract.withdraw(4 * ONE_GEN)
    config = contract.get_config()
    assert config["cash"] == 6 * ONE_GEN
    assert config["total_shares"] == 6 * ONE_GEN


def test_withdraw_rejects_too_much(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    direct_vm.value = 0
    with direct_vm.expect_revert("not enough shares"):
        contract.withdraw(11 * ONE_GEN)


def test_propose_buy_is_pending(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    pid = open_buy(contract, direct_vm)
    row = contract.get_proposal(int(pid))
    assert row["found"] is True
    assert row["status"] == "pending"
    assert row["action"] == "buy"
    assert int(row["amount"]) == ONE_GEN


def test_propose_rejects_over_cap(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    direct_vm.value = 0
    with direct_vm.expect_revert("amount exceeds free cash or position cap"):
        contract.propose("bitcoin", "buy", 2 * ONE_GEN, THESIS, sources(), COUNTERPARTY, 120)


def test_review_approve_reserves(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    pid = open_buy(contract, direct_vm)
    mock_review(direct_vm, "approve")
    verdict = contract.review(int(pid))
    assert verdict == "approve"
    row = contract.get_proposal(int(pid))
    assert row["status"] == "approved"
    assert contract.get_config()["reserved"] == ONE_GEN
    assert contract.get_config()["free"] == 9 * ONE_GEN


def test_review_reject_does_not_reserve(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    pid = open_buy(contract, direct_vm)
    mock_review(direct_vm, "reject")
    verdict = contract.review(int(pid))
    assert verdict == "reject"
    assert contract.get_proposal(int(pid))["status"] == "rejected"
    assert contract.get_config()["reserved"] == 0


def test_execute_buy_spends_cash(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    pid = open_buy(contract, direct_vm)
    mock_review(direct_vm, "approve")
    contract.review(int(pid))
    direct_vm.value = 0
    contract.execute(int(pid))
    row = contract.get_proposal(int(pid))
    config = contract.get_config()
    assert row["status"] == "executed"
    assert config["cash"] == 9 * ONE_GEN
    assert config["reserved"] == 0
    assert int(row["spent"]) == ONE_GEN - (ONE_GEN * 20) // 10000


def test_repay_returns_cash(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    pid = open_buy(contract, direct_vm)
    mock_review(direct_vm, "approve")
    contract.review(int(pid))
    direct_vm.value = 0
    contract.execute(int(pid))
    direct_vm.value = ONE_GEN
    contract.repay(int(pid))
    row = contract.get_proposal(int(pid))
    assert int(row["returned"]) == ONE_GEN
    assert contract.get_config()["cash"] == 10 * ONE_GEN


def test_report_met(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    pid = open_buy(contract, direct_vm)
    mock_review(direct_vm, "approve")
    contract.review(int(pid))
    direct_vm.value = 0
    contract.execute(int(pid))
    direct_vm.clear_mocks()
    direct_vm.mock_web(r"data\.example/btc", {"status": 200, "body": "The bitcoin allocation was completed."})
    direct_vm.mock_llm(r"already executed allocation", "met")
    outcome = contract.report(int(pid), SOURCE)
    assert outcome == "met"
    assert contract.get_proposal(int(pid))["status"] == "reported"


def test_release_before_expiry_fails(direct_vm, direct_deploy, direct_owner):
    contract = deploy(direct_vm, direct_deploy, direct_owner)
    deposit(contract, direct_vm, 10)
    pid = open_buy(contract, direct_vm)
    mock_review(direct_vm, "approve")
    contract.review(int(pid))
    with direct_vm.expect_revert("proposal is still inside its window"):
        contract.release_expired(int(pid))