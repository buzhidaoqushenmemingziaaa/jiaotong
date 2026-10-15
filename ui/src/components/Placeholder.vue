<script setup lang="ts">
defineProps<{
  title: string
  desc?: string
}>()
</script>

<template>
  <div class="placeholder">
    <el-empty description=" ">
      <template #image>
        <el-icon :size="56" color="#dcdfe6"><Document /></el-icon>
      </template>
      <h2 class="ph-title">{{ title }}</h2>
      <p class="ph-desc">{{ desc || '本模块待开发，下一步将接入实际功能。' }}</p>
    </el-empty>
  </div>
</template>

<style scoped>
.placeholder {
  background: #fff;
  border-radius: 6px;
  padding: 48px 24px;
  min-height: 60vh;
}
.ph-title {
  margin: 12px 0 8px;
  font-size: 20px;
  color: #303133;
}
.ph-desc {
  margin: 0;
  color: #909399;
  font-size: 14px;
}
</style>
