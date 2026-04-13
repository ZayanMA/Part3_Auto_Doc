'use client'
import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { postDemoGenerateZip } from '@/lib/api'
import { useDemoStore } from '@/lib/useDemoStore'

export default function ZipUploadForm() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { startJob } = useDemoStore()

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setFile(accepted[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/zip': ['.zip'], 'application/x-zip-compressed': ['.zip'] },
    maxFiles: 1,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) { setError('Please select a ZIP file'); return }
    setError('')
    setLoading(true)
    try {
      const repoName = file.name.replace('.zip', '')
      const res = await postDemoGenerateZip(file)
      startJob(res.job_id, repoName)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        <input {...getInputProps()} />
        {file ? (
          <div>
            <p className="font-medium text-gray-900">{file.name}</p>
            <p className="text-sm text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
        ) : (
          <div>
            <p className="text-gray-600">Drag & drop a ZIP file here, or click to browse</p>
            <p className="text-sm text-gray-400 mt-1">.zip files only</p>
          </div>
        )}
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <button
        type="submit"
        disabled={loading || !file}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium py-2 px-4 rounded-md text-sm transition-colors"
      >
        {loading ? 'Uploading...' : 'Generate Documentation'}
      </button>
    </form>
  )
}
