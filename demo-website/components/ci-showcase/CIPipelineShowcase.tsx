'use client'
import { useState } from 'react'
import AnimatedTerminal from './AnimatedTerminal'
import WorkflowYamlPanel from './WorkflowYamlPanel'

const STEPS = [
  { label: 'Detect Key', icon: '🔍' },
  { label: 'Trigger Gen', icon: '🚀' },
  { label: 'Poll Status', icon: '⏳' },
  { label: 'Push to Forge', icon: '📤' },
]

export default function CIPipelineShowcase() {
  const [activeStep, setActiveStep] = useState(0)

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center justify-center gap-0">
        {STEPS.map((step, i) => (
          <div key={i} className="flex items-center">
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
              i <= activeStep
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-500'
            }`}>
              <span>{step.icon}</span>
              <span className="hidden sm:inline">{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`h-0.5 w-6 sm:w-12 mx-1 ${i < activeStep ? 'bg-blue-600' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">CI Run</h3>
          <AnimatedTerminal onStepChange={setActiveStep} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Workflow YAML</h3>
          <WorkflowYamlPanel activeStep={activeStep} />
        </div>
      </div>
    </div>
  )
}
