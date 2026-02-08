#!/usr/bin/env python3
"""Script de prueba para validar la función normalize_sku.

Este script prueba diferentes formatos de SKU para asegurar que la normalización funcione correctamente.
"""

def normalize_sku(sku_value) -> str:
    """Normaliza un valor SKU removiendo comillas, espacios extras y convirtiendo a string."""
    if sku_value is None:
        return ""

    # Convertir a string si es necesario
    sku_str = str(sku_value)

    # Remover espacios al inicio y final
    sku_str = sku_str.strip()

    # Remover comillas dobles y simples al inicio y final
    sku_str = sku_str.strip('"').strip("'")

    # Remover espacios nuevamente por si había comillas con espacios
    sku_str = sku_str.strip()

    return sku_str


def test_normalize_sku():
    """Ejecuta pruebas de la función normalize_sku con diferentes casos."""

    test_cases = [
        # (input, expected_output, description)
        ("000013", "000013", "SKU sin comillas"),
        ('"000013"', "000013", "SKU con comillas dobles"),
        ("'000013'", "000013", "SKU con comillas simples"),
        (" 000013 ", "000013", "SKU con espacios"),
        (' "000013" ', "000013", "SKU con comillas y espacios"),
        ("000-013", "000-013", "SKU con guiones"),
        ('"000-013"', "000-013", "SKU con guiones y comillas dobles"),
        ("'000-013'", "000-013", "SKU con guiones y comillas simples"),
        (13, "13", "SKU numérico (int)"),
        (13.0, "13.0", "SKU numérico (float)"),
        ("", "", "SKU vacío"),
        (None, "", "SKU None"),
        ('  "  000013  "  ', "000013", "SKU con múltiples espacios y comillas"),
    ]

    print("Ejecutando pruebas de normalize_sku()...\n")

    passed = 0
    failed = 0

    for input_val, expected, description in test_cases:
        result = normalize_sku(input_val)
        status = "✓ PASS" if result == expected else "✗ FAIL"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} - {description}")
        print(f"  Input:    {repr(input_val)}")
        print(f"  Expected: {repr(expected)}")
        print(f"  Got:      {repr(result)}")
        print()

    print(f"\nResultados: {passed} pasaron, {failed} fallaron de {len(test_cases)} pruebas")

    if failed == 0:
        print("✓ Todas las pruebas pasaron exitosamente!")
        return True
    else:
        print("✗ Algunas pruebas fallaron")
        return False


if __name__ == "__main__":
    success = test_normalize_sku()
    exit(0 if success else 1)
