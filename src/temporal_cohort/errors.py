"""Public-contract data and validation failures."""


class ContractError(ValueError):
    """The requested input cannot be interpreted under the public contract."""
