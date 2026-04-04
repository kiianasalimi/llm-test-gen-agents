from impl.cut.calculator import *



def test_agent2_negative_exponent_power():
    """Test power with negative exponent to check float result."""
    assert power(2, -1) == 0.5

def test_agent2_large_integer_modulo():
    """Test modulo with very large integers for overflow or precision issues."""
    assert modulo(10**18, 3) == 1

def test_agent2_sqrt_zero():
    """Test sqrt with zero input to ensure it returns zero without error."""
    assert sqrt(0) == 0.0

def test_agent2_integer_divide_negative():
    """Test integer division with negative numbers to check floor behavior."""
    assert integer_divide(-7, 3) == -3

def test_agent2_history_after_clear():
    """Test that clear_history resets history and accumulator correctly."""
    calc = Calculator()
    calc.add(1, 2)
    calc.clear_history()
    assert calc.operation_count() == 0
    assert calc.accumulator == 0.0
    assert calc.last_result() is None