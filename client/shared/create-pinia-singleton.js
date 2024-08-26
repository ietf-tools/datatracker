import { createPinia } from 'pinia'

export function createPiniaSingleton(){
  window.pinia = window.pinia ?? createPinia()
  return window.pinia
}
