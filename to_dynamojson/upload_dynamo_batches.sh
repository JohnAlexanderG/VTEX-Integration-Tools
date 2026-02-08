#!/bin/bash

# Script para subir todos los archivos batch a DynamoDB
# Autor: Generado automáticamente
# Fecha: $(date)

echo "🚀 Iniciando carga masiva a DynamoDB..."
echo "📊 Total de lotes a procesar: 764"
echo ""

# Contadores
success_count=0
error_count=0
total_batches=764

# Archivo de log para errores
error_log="dynamo_upload_errors_$(date +%Y%m%d_%H%M%S).log"
success_log="dynamo_upload_success_$(date +%Y%m%d_%H%M%S).log"

echo "📝 Logs de errores: $error_log"
echo "📝 Logs de éxito: $success_log"
echo ""

# Función para mostrar progreso
show_progress() {
    local current=$1
    local total=$2
    local percentage=$((current * 100 / total))
    local filled=$((percentage / 2))
    local empty=$((50 - filled))

    printf "\r["
    printf "%*s" $filled | tr ' ' '='
    printf "%*s" $empty | tr ' ' '-'
    printf "] %d%% (%d/%d)" $percentage $current $total
}

echo "⏳ Comenzando carga de lotes..."
echo ""

# Loop principal para procesar todos los lotes
for i in $(seq -f "%03g" 1 764); do
    batch_file="sku-vtex_items_batch_${i}.json"

    # Verificar que el archivo existe
    if [ ! -f "$batch_file" ]; then
        echo "❌ Error: Archivo $batch_file no encontrado" | tee -a "$error_log"
        ((error_count++))
        continue
    fi

    # Ejecutar el comando AWS
    if aws dynamodb batch-write-item --request-items file://"$batch_file" >> "$success_log" 2>> "$error_log"; then
        ((success_count++))
        echo "✅ Lote $i procesado exitosamente" >> "$success_log"
    else
        ((error_count++))
        echo "❌ Error procesando lote $i" | tee -a "$error_log"
    fi

    # Mostrar progreso
    current_batch=$((10#$i))  # Convertir a decimal para evitar problemas con números con 0 inicial
    show_progress $current_batch $total_batches

    # Pausa para evitar rate limiting de AWS (1 segundo entre requests)
    sleep 1
done

echo ""
echo ""
echo "🎉 ¡Proceso completado!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Lotes exitosos: $success_count"
echo "❌ Lotes con error: $error_count"
echo "📊 Total procesado: $((success_count + error_count)) de $total_batches"
echo ""

if [ $error_count -eq 0 ]; then
    echo "🚀 ¡Todos los lotes se cargaron exitosamente!"
    echo "📝 Detalles en: $success_log"
else
    echo "⚠️  Algunos lotes tuvieron errores."
    echo "📝 Revisa los errores en: $error_log"
    echo "📝 Lotes exitosos en: $success_log"
    echo ""
    echo "💡 Para reintentar solo los lotes que fallaron, revisa el archivo de errores."
fi

echo ""
echo "📋 Resumen de archivos generados:"
echo "   • $success_log (lotes exitosos)"
echo "   • $error_log (errores encontrados)"