interface Props {
  slot: string
}

export function AdSlot({ slot }: Props) {
  return (
    <div className='rounded-xl border border-gray-200 bg-white p-6 flex flex-col items-center justify-center min-h-24'>
      <div className='flex items-center gap-2 mb-3'>
        <span className='text-xs font-semibold bg-gray-100 text-gray-500 px-2 py-1 rounded-full'>AD</span>
      </div>
      <p className='text-sm text-gray-400'>광고 영역</p>
      <p className='text-xs text-gray-300 mt-2'>[{slot}]</p>
    </div>
  )
}
