<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter, type RouteRecordRaw } from 'vue-router'
import { Fold, Menu as IconMenu, Expand, Connection, Monitor } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const isCollapse = ref(false)
const activeMenu = computed(() => route.path)

// 从路由表提取带 meta.title 的子路由作为菜单
const menuItems = computed(() => {
  const layoutRoute = router.options.routes.find((r) => r.path === '/')
  const children = (layoutRoute?.children as RouteRecordRaw[]) || []
  return children.filter((c) => c.meta?.title)
})

const currentTitle = computed(() => (route.meta.title as string) || '首页')

async function toggleBackend() {
  // 验收演示用：一键切换 mock ↔ 真后端，前端代码不改
  if (app.isMock) {
    app.switchBackend('', false)
    ElMessage.success('已切换到真后端（同源）')
  } else {
    app.switchBackend('http://127.0.0.1:8800', true)
    ElMessage.success('已切换到 Mock 后端（8800）')
  }
  await app.checkHealth()
}

onMounted(() => {
  app.checkHealth()
})
</script>

<template>
  <el-container class="layout-root">
    <el-aside :width="isCollapse ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)'" class="layout-aside">
      <div class="logo">
        <el-icon :size="22"><Connection /></el-icon>
        <span v-show="!isCollapse" class="logo-text">城轨决策</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        class="layout-menu"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="'/' + item.path">
          <el-icon><component :is="item.meta?.icon" /></el-icon>
          <template #title>{{ item.meta?.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="isCollapse = !isCollapse">
            <component :is="isCollapse ? Expand : Fold" />
          </el-icon>
          <span class="page-title">{{ currentTitle }}</span>
        </div>
        <div class="header-right">
          <el-tag :type="app.isMock ? 'warning' : 'success'" size="small" effect="dark">
            <el-icon style="vertical-align: middle"><Monitor /></el-icon>
            {{ app.isMock ? 'Mock 后端' : '真后端' }}
          </el-tag>
          <el-tag
            :type="app.cases.length ? 'success' : 'danger'"
            size="small"
            effect="plain"
          >
            {{ app.cases.length ? `算例 ${app.cases.length}` : app.lastError || '未连接' }}
          </el-tag>
          <el-button size="small" plain @click="toggleBackend">切换后端</el-button>
        </div>
      </el-header>

      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <component :is="Component" />
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout-root {
  height: 100%;
}
.layout-aside {
  background: #001529;
  transition: width 0.2s;
}
.logo {
  height: var(--header-height);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
}
.layout-menu {
  background: transparent;
  border-right: none;
}
.layout-menu:not(.el-menu--collapse) {
  width: var(--sidebar-width);
}
.layout-header {
  height: var(--header-height);
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: #606266;
}
.page-title {
  font-size: 16px;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.layout-main {
  padding: 16px;
  background: #f5f7fa;
  overflow: auto;
}
:deep(.el-menu) {
  background: transparent;
}
:deep(.el-menu-item) {
  color: #b7bdc3;
}
:deep(.el-menu-item.is-active) {
  color: #fff;
  background: #177cff;
}
:deep(.el-menu-item:hover) {
  background: #002140;
}
</style>
