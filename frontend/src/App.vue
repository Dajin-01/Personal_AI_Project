

<script setup lang="ts">
import { onMounted, ref } from 'vue'

type Project = {
  id: number
  name: string
}

const projects = ref<Project[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const response = await fetch('/projects')
    if (!response.ok) {
      throw new Error(`프로젝트를 불러오지 못했어요. (${response.status})`)
    }

    projects.value = await response.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '요청에 실패했어요.'
  } finally {
    loading.value = false
  }
})

type ProjectDocument = {
  id: number
  title: string
  content: string
  summary: string | null
}

const selectedDocument = ref<ProjectDocument | null>(null)

const selectedProject = ref<Project | null>(null)
const documents = ref<ProjectDocument[]>([])
const documentsLoading = ref(false)
const documentsError = ref('')

async function loadDocuments(project: Project) {
  selectDocument(null)
  selectedProject.value = project
  documents.value = []
  documentsError.value = ''
  documentSaveError.value = ''
  documentsLoading.value = true

  try {
    const response = await fetch(`/projects/${project.id}/documents`)
    if (!response.ok) {
      throw new Error(`문서를 불러오지 못했어요. (${response.status})`)
    }

    documents.value = await response.json()
  } catch (err) {
    documentsError.value =
      err instanceof Error ? err.message : '요청에 실패했어요.'
  } finally {
    documentsLoading.value = false
  }
}

const summaryBusy = ref(false)
const summaryTaskId = ref('')
const summaryState = ref('')
const summaryError = ref('')

function selectDocument(document: ProjectDocument | null) {
  selectedDocument.value = document
  summaryTaskId.value = ''
  summaryState.value = ''
  summaryError.value = ''
}

async function requestSummary() {
  const project = selectedProject.value
  const document = selectedDocument.value
  if (!project || !document || summaryBusy.value) return

  summaryBusy.value = true
  summaryTaskId.value = ''
  summaryState.value = ''
  summaryError.value = ''

  try {
    const response = await fetch(
      `/projects/${project.id}/documents/${document.id}/summary-jobs`,
      { method: 'POST' },
    )

    if (!response.ok) {
      throw new Error(`요약 요청에 실패했어요. (${response.status})`)
    }

    const data = await response.json()
    summaryTaskId.value = data.task_id
  } catch (err) {
    summaryError.value =
      err instanceof Error ? err.message : '요약 요청에 실패했어요.'
  } finally {
    summaryBusy.value = false
  }
  if (summaryTaskId.value) {
  void pollSummary(summaryTaskId.value)
}
}

async function checkSummary() {
  const project = selectedProject.value
  const document = selectedDocument.value
  const taskId = summaryTaskId.value

  if (!project || !document || !taskId || summaryBusy.value) return

  summaryBusy.value = true
  summaryError.value = ''

  try {
    const statusResponse = await fetch(`/summary-jobs/${taskId}`)
    if (!statusResponse.ok) {
      throw new Error(`작업 상태를 확인하지 못했어요. (${statusResponse.status})`)
    }

    const job = await statusResponse.json()
    summaryState.value = job.state

    if (job.state === 'SUCCESS') {
      const documentResponse = await fetch(
        `/projects/${project.id}/documents/${document.id}`,
      )
      if (!documentResponse.ok) {
        throw new Error(`저장된 요약을 불러오지 못했어요. (${documentResponse.status})`)
      }

      const updatedDocument: ProjectDocument = await documentResponse.json()
      document.summary = updatedDocument.summary
    }
  } catch (err) {
    summaryError.value =
      err instanceof Error ? err.message : '상태 확인에 실패했어요.'
  } finally {
    summaryBusy.value = false
  }
}

async function pollSummary(taskId: string) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    await new Promise<void>((resolve) => setTimeout(resolve, 2000))

    if (
      summaryTaskId.value !== taskId ||
      summaryError.value ||
      ['SUCCESS', 'FAILURE', 'REVOKED'].includes(summaryState.value)
    ) {
      return
    }

    await checkSummary()
  }
}

const newTitle = ref('')
const newContent = ref('')
const documentSaving = ref(false)
const documentSaveError = ref('')

async function createDocument() {
  const project = selectedProject.value
  if (!project || documentSaving.value) return

  const title = newTitle.value.trim()
  const content = newContent.value

  if (!title || !content.trim()) {
    documentSaveError.value = '제목과 본문을 입력해 주세요.'
    return
  }

  documentSaving.value = true
  documentSaveError.value = ''

  try {
    const response = await fetch(`/projects/${project.id}/documents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content }),
    })

    if (!response.ok) {
      throw new Error(`문서를 저장하지 못했어요. (${response.status})`)
    }

    const createdDocument: ProjectDocument = await response.json()
    documents.value.push(createdDocument)
    newTitle.value = ''
    newContent.value = ''
  } catch (err) {
    documentSaveError.value =
      err instanceof Error ? err.message : '문서 저장에 실패했어요.'
  } finally {
    documentSaving.value = false
  }
}

const newProjectName = ref('')
const projectSaving = ref(false)
const projectSaveError = ref('')

async function createProject() {
  if (projectSaving.value) return

  const name = newProjectName.value.trim()
  if (!name) {
    projectSaveError.value = '프로젝트 이름을 입력해 주세요.'
    return
  }

  projectSaving.value = true
  projectSaveError.value = ''

  try {
    const response = await fetch('/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })

    if (!response.ok) {
      throw new Error(`프로젝트를 저장하지 못했어요. (${response.status})`)
    }

    const createdProject: Project = await response.json()
    projects.value.push(createdProject)
    newProjectName.value = ''
  } catch (err) {
    projectSaveError.value =
      err instanceof Error ? err.message : '프로젝트 저장에 실패했어요.'
  } finally {
    projectSaving.value = false
  }
}
</script>

<template>
  <main>
    <h1>프로젝트 목록</h1>

    <form v-if="!loading && !error" @submit.prevent="createProject">
      <label>
        새 프로젝트 이름
        <input
          v-model="newProjectName"
          required
          maxlength="100"
          :disabled="projectSaving"
        />
      </label>

      <button type="submit" :disabled="projectSaving">
        {{ projectSaving ? '저장 중…' : '프로젝트 등록' }}
      </button>

      <p v-if="projectSaveError" role="alert">{{ projectSaveError }}</p>
    </form>

    <p v-if="loading" role="status">불러오는 중…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <p v-else-if="projects.length === 0">등록된 프로젝트가 없어요.</p>

    <ul v-else>
      <li v-for="project in projects" :key="project.id">
        <button
          type="button"
          :disabled="documentsLoading || summaryBusy || documentSaving"
          @click="loadDocuments(project)"
        >
          {{ project.name }}
        </button>
      </li>
    </ul>

    <section v-if="selectedProject">
      <h2>{{ selectedProject.name }}의 문서</h2>

      <form v-if="!documentsLoading && !documentsError" @submit.prevent="createDocument">
        <fieldset :disabled="documentSaving">
          <legend>새 문서 등록</legend>

          <p>
            <label>
              제목
              <input v-model="newTitle" required maxlength="200" />
            </label>
          </p>

          <p>
            <label>
              본문
              <textarea v-model="newContent" required rows="4"></textarea>
            </label>
          </p>

          <button type="submit">
            {{ documentSaving ? '저장 중…' : '문서 등록' }}
          </button>
        </fieldset>

        <p v-if="documentSaveError" role="alert">{{ documentSaveError }}</p>
      </form>

      <p v-if="documentsLoading" role="status">문서를 불러오는 중…</p>
      <p v-else-if="documentsError" role="alert">{{ documentsError }}</p>
      <p v-else-if="documents.length === 0">등록된 문서가 없어요.</p>

      <ul v-else>
        <li v-for="document in documents" :key="document.id">
          <button
            type="button"
            :disabled="summaryBusy"
            @click="selectDocument(document)"
          >
            {{ document.title }}
          </button>
        </li>
      </ul>

      <article v-if="selectedDocument">
        <h3>{{ selectedDocument.title }}</h3>

        <h4>본문</h4>
        <p>{{ selectedDocument.content }}</p>

        <h4>AI 요약</h4>
        <p>{{ selectedDocument.summary ?? '아직 생성된 요약이 없어요.' }}</p>

        <button type="button" :disabled="summaryBusy" @click="requestSummary">
          {{ summaryBusy ? '처리 중…' : '요약 요청' }}
        </button>

        <p v-if="summaryError" role="alert">{{ summaryError }}</p>

        <div v-if="summaryTaskId">
          <p role="status">작업 상태 {{ summaryState || '접수됨' }}</p>
          <p>작업 ID {{ summaryTaskId }}</p>
          <button type="button" :disabled="summaryBusy" @click="checkSummary">
            상태 확인
          </button>
        </div>     
      </article>
    </section>
  </main>
</template>
