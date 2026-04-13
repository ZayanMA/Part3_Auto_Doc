'use client'
import dynamic from 'next/dynamic'
import { useMemo } from 'react'

const CodeMirror = dynamic(() => import('@uiw/react-codemirror'), { ssr: false })

// ${{ }} syntax is kept as a string literal — not a JS template expression
const YAML_CONTENT = [
  'name: AutoDoc Generate and Push',
  '',
  'on:',
  '  workflow_call:',
  '    inputs:',
  '      confluence_space_key:',
  '        required: true',
  '        type: string',
  '    secrets:',
  '      AUTODOC_API_URL:',
  '        required: true',
  '      AUTODOC_API_KEY:',
  '        required: true',
  '      AUTODOC_WEBHOOK_URL:',
  '        required: true',
  '      AUTODOC_WEBHOOK_SECRET:',
  '        required: true',
  '',
  'jobs:',
  '  generate-and-push:',
  '    name: Generate docs and push to Forge',
  '    runs-on: ubuntu-latest',
  '    if: github.event.pull_request.merged == true',
  '',
  '    steps:',
  '      - name: Install httpx',
  '        run: pip install httpx',
  '',
  '      - name: Detect Jira issue key',
  '        id: jira',
  '        run: |',
  '          KEY="${{ inputs.jira_issue_key }}"',
  '          if [ -z "$KEY" ]; then',
  '            KEY=$(echo "${{ github.event.pull_request.body }}" | grep -oP \'[A-Z]+-\\d+\' | head -1)',
  '          fi',
  '          echo "key=$KEY" >> "$GITHUB_OUTPUT"',
  '',
  '      - name: Trigger documentation generation',
  '        id: trigger',
  '        run: python3 trigger.py',
  '',
  '      - name: Poll for completion',
  '        id: poll',
  '        run: python3 poll.py',
  '',
  '      - name: Push documentation to Forge webhook',
  '        run: python3 push_webhook.py',
].join('\n')

// Step to line number mapping (0-indexed)
const STEP_LINES: Record<number, [number, number]> = {
  0: [35, 42],  // Install httpx + Detect key
  1: [43, 52],  // Trigger generation
  2: [53, 62],  // Poll for completion
  3: [63, 68],  // Push webhook
}

interface Props {
  activeStep: number
}

export default function WorkflowYamlPanel({ activeStep }: Props) {
  return (
    <div className="bg-gray-950 rounded-xl overflow-hidden shadow-xl">
      <div className="bg-gray-800 px-4 py-2 flex items-center gap-2">
        <span className="text-gray-400 text-xs font-mono">.github/workflows/autodoc.yml</span>
      </div>
      <div className="overflow-auto" style={{ maxHeight: 320 }}>
        <CodeMirror
          value={YAML_CONTENT}
          height="320px"
          theme="dark"
          readOnly
          basicSetup={{ lineNumbers: true, foldGutter: false, highlightActiveLine: false }}
        />
      </div>
    </div>
  )
}
