import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import Layout from '@/layout/index.vue'

// 路由：八大功能模块 + 布局外壳
// 占位页先统一渲染“开发中”，后续步骤逐步填充
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: Layout,
    redirect: '/config',
    children: [
      {
        path: 'line',
        name: 'line',
        component: () => import('@/views/LineView.vue'),
        meta: { title: '线路建模', icon: 'Share' },
      },
      {
        path: 'config',
        name: 'config',
        component: () => import('@/views/ConfigView.vue'),
        meta: { title: '参数配置', icon: 'Setting' },
      },
      {
        path: 'solve',
        name: 'solve',
        component: () => import('@/views/SolveView.vue'),
        meta: { title: '方案求解', icon: 'VideoPlay' },
      },
      {
        path: 'results',
        name: 'results',
        component: () => import('@/views/ResultsView.vue'),
        meta: { title: '结果总览', icon: 'DataAnalysis' },
      },
      {
        path: 'viz',
        name: 'viz',
        component: () => import('@/views/VisualizeView.vue'),
        meta: { title: '运行可视化', icon: 'Position' },
      },
      {
        path: 'compare',
        name: 'compare',
        component: () => import('@/views/CompareView.vue'),
        meta: { title: '方案对比', icon: 'ScaleToOriginal' },
      },
      {
        path: 'sweep',
        name: 'sweep',
        component: () => import('@/views/SweepView.vue'),
        meta: { title: '敏感性分析', icon: 'TrendCharts' },
      },
      {
        path: 'export',
        name: 'export',
        component: () => import('@/views/ExportView.vue'),
        meta: { title: '报告导出', icon: 'Document' },
      },
      {
        path: 'diagnose',
        name: 'diagnose',
        component: () => import('@/views/DiagnoseView.vue'),
        meta: { title: '诊断与帮助', icon: 'Warning' },
      },
      {
        path: 'test',
        name: 'test',
        component: () => import('@/views/TestView.vue'),
        meta: { title: '测试运行', icon: 'Cpu' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/config' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  const title = (to.meta.title as string) || '城轨列车开行方案决策系统'
  document.title = `${title} · 城轨决策`
})

export default router
