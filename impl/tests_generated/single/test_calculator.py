import pytest
from impl.cut.calculator import *

def test_add():
    """Test addition of two positive numbers."""
    assert add(2, 3) == 5

def test_subtract():
    """Test subtraction resulting in a negative number."""
    assert subtract(3, 5) == -2

def test_multiply_zero():
    """Test multiplication by zero."""
    assert multiply(5, 0) == 0

def test_divide_normal():
    """Test division with valid inputs."""
    assert divide(6, 3) == 2

def test_divide_by_zero():
    """Test division by zero raises ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError):
        divide(5, 0)

def test_power_negative_exponent():
    """Test power function with negative exponent."""
    assert power(2, -1) == 0.5

def test_sqrt_negative():
    """Test square root of a negative number raises ValueError."""
    with pytest.raises(ValueError):
        sqrt(-1)

def test_calculator_operation_history():
    """Test Calculator records operations and handles errors."""
    calc = Calculator()
    calc.add(2, 3)
    assert calc.history == [{'op': '2+3', 'result': 5}]
    assert calc.accumulator == 5.0
    with pytest.raises(TypeError):
        calc.add("a", 2)
    assert calc.history == [{'op': '2+3', 'result': 5}]
    calc.clear_history()
    assert calc.history == []
    assert calc.accumulator == 0.0
    assert calc.operation_count() == 0