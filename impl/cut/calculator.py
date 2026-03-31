"""Calculator module — the Code Under Test (CUT) for test generation experiments."""

import math


class CalculatorError(Exception):
    """Base exception raised for domain-level calculator errors."""


def _check_numeric(*values):
    """Raise TypeError if any value is not int or float."""
    for v in values:
        if not isinstance(v, (int, float)):
            raise TypeError(
                f"Operands must be numeric (int or float), got {type(v).__name__!r}"
            )


# ---------------------------------------------------------------------------
# Module-level stateless functions
# ---------------------------------------------------------------------------

def add(a, b):
    """Return the sum a + b."""
    _check_numeric(a, b)
    return a + b


def subtract(a, b):
    """Return the difference a - b."""
    _check_numeric(a, b)
    return a - b


def multiply(a, b):
    """Return the product a * b."""
    _check_numeric(a, b)
    return a * b


def divide(a, b):
    """Return the quotient a / b.

    Raises:
        ZeroDivisionError: if b is zero.
    """
    _check_numeric(a, b)
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b


def power(base, exponent):
    """Return base raised to exponent (base ** exponent)."""
    _check_numeric(base, exponent)
    return base ** exponent


def sqrt(x):
    """Return the non-negative square root of x.

    Raises:
        ValueError: if x is negative.
    """
    _check_numeric(x)
    if x < 0:
        raise ValueError(f"math domain error: cannot take square root of {x}")
    return math.sqrt(x)


def modulo(a, b):
    """Return the remainder of a divided by b (a % b).

    Raises:
        ZeroDivisionError: if b is zero.
    """
    _check_numeric(a, b)
    if b == 0:
        raise ZeroDivisionError("modulo by zero")
    return a % b


def integer_divide(a, b):
    """Return the floor division of a by b (a // b).

    Raises:
        ZeroDivisionError: if b is zero.
    """
    _check_numeric(a, b)
    if b == 0:
        raise ZeroDivisionError("integer division by zero")
    return a // b


# ---------------------------------------------------------------------------
# Stateful Calculator class
# ---------------------------------------------------------------------------

class Calculator:
    """A stateful calculator that records a history of operations."""

    def __init__(self):
        self._history = []  # list of {"op": str, "result": number}
        self._accumulator = 0.0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def history(self):
        """Return a copy of the operation history (list of dicts)."""
        return list(self._history)

    @property
    def accumulator(self):
        """Return the current accumulator value."""
        return self._accumulator

    # ------------------------------------------------------------------
    # Arithmetic methods — each delegates to the module-level functions
    # so both the class and standalone paths can be tested independently.
    # ------------------------------------------------------------------

    def _record(self, op: str, result):
        self._history.append({"op": op, "result": result})
        self._accumulator = result
        return result

    def add(self, a, b):
        """Add a and b, record in history, return result."""
        return self._record(f"{a}+{b}", add(a, b))

    def subtract(self, a, b):
        """Subtract b from a, record in history, return result."""
        return self._record(f"{a}-{b}", subtract(a, b))

    def multiply(self, a, b):
        """Multiply a and b, record in history, return result."""
        return self._record(f"{a}*{b}", multiply(a, b))

    def divide(self, a, b):
        """Divide a by b, record in history, return result."""
        return self._record(f"{a}/{b}", divide(a, b))

    def power(self, base, exponent):
        """Raise base to exponent, record in history, return result."""
        return self._record(f"{base}**{exponent}", power(base, exponent))

    def sqrt(self, x):
        """Compute sqrt of x, record in history, return result."""
        return self._record(f"sqrt({x})", sqrt(x))

    def modulo(self, a, b):
        """Compute a % b, record in history, return result."""
        return self._record(f"{a}%{b}", modulo(a, b))

    # ------------------------------------------------------------------
    # History helpers
    # ------------------------------------------------------------------

    def last_result(self):
        """Return the result of the most recent operation, or None."""
        return self._history[-1]["result"] if self._history else None

    def clear_history(self):
        """Clear the operation history and reset the accumulator to 0."""
        self._history.clear()
        self._accumulator = 0.0

    def operation_count(self):
        """Return the total number of operations recorded."""
        return len(self._history)
