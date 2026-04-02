import pytest
from impl.cut.calculator import *



def test_edge_case_tester_none_input():
    """Test None input raises TypeError in add and Calculator.add."""
    with pytest.raises(TypeError, match="Operands must be numeric"):
        add(None, 1)
    calc = Calculator()
    with pytest.raises(TypeError, match="Operands must be numeric"):
        calc.add(None, 1)

def test_edge_case_tester_empty_string():
    """Test empty string input raises TypeError in subtract and Calculator.subtract."""
    with pytest.raises(TypeError, match="Operands must be numeric"):
        subtract("", 1)
    calc = Calculator()
    with pytest.raises(TypeError, match="Operands must be numeric"):
        calc.subtract("", 1)

def test_edge_case_tester_zero_division():
    """Test zero division raises ZeroDivisionError in divide and Calculator.divide."""
    with pytest.raises(ZeroDivisionError, match="division by zero"):
        divide(1, 0)
    calc = Calculator()
    with pytest.raises(ZeroDivisionError, match="division by zero"):
        calc.divide(1, 0)

def test_edge_case_tester_sqrt_negative():
    """Test negative input raises ValueError in sqrt and Calculator.sqrt."""
    with pytest.raises(ValueError, match="math domain error"):
        sqrt(-1)
    calc = Calculator()
    with pytest.raises(ValueError, match="math domain error"):
        calc.sqrt(-1)

def test_edge_case_tester_very_large_exponent():
    """Test very large exponent causes OverflowError in power and Calculator.power."""
    with pytest.raises(OverflowError):
        power(2, 1e300)
    calc = Calculator()
    with pytest.raises(OverflowError):
        calc.power(2, 1e300)

def test_error_tester_add_non_numeric():
    """Test add with non-numeric arguments raises TypeError."""
    with pytest.raises(TypeError):
        add("a", 1)

def test_error_tester_divide_by_zero():
    """Test divide by zero raises ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)

def test_error_tester_sqrt_negative():
    """Test sqrt of negative raises ValueError."""
    with pytest.raises(ValueError):
        sqrt(-1)

def test_error_tester_calculator_modulo_non_numeric():
    """Test Calculator.modulo with non-numeric raises TypeError."""
    calc = Calculator()
    with pytest.raises(TypeError):
        calc.modulo("a", 1)

def test_error_tester_integer_divide_by_zero():
    """Test integer_divide by zero raises ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError):
        integer_divide(1, 0)