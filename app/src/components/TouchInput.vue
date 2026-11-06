<script setup>
import {ref} from 'vue'
defineProps({modelValue:{type:String,default:''},label:String,placeholder:String,maxlength:{type:Number,default:120}})
const emit=defineEmits(['update:modelValue'])
const open=ref(false)
const rows=['1234567890','qwertyuiop','asdfghjklñ','zxcvbnm']
</script>
<template><div class="touch-field"><label>{{label}}<input data-trace-private :value="modelValue" @input="emit('update:modelValue',$event.target.value)" @focus="open=true" inputmode="none" autocomplete="off" :maxlength="maxlength" :placeholder="placeholder"></label><div v-if="open" class="campus-keyboard" aria-label="Teclado táctil de texto"><div class="keyboard-row" v-for="row in rows" :key="row"><button data-trace-private type="button" v-for="letter in row" :key="letter" @click="emit('update:modelValue',(modelValue+letter).slice(0,maxlength))">{{letter}}</button></div><div class="keyboard-row"><button data-trace-private type="button" @click="emit('update:modelValue',(modelValue+' ').slice(0,maxlength))">ESPACIO</button><button data-trace-private type="button" @click="emit('update:modelValue',modelValue.slice(0,-1))">⌫</button><button data-trace-private type="button" @click="open=false">LISTO ✓</button></div></div></div></template>
