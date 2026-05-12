import VideoVoucherCreateView from './VideoVoucherCreateView';

interface VideoVoucherDetailViewProps {
  runId: number | null;
  campaignId: number | null;
  onBackToVouchers: () => void;
}

export default function VideoVoucherDetailView({ runId, campaignId, onBackToVouchers }: VideoVoucherDetailViewProps) {
  return (
    <VideoVoucherCreateView
      runId={runId}
      readOnly
      detailCampaignId={campaignId}
      onBackToVouchers={onBackToVouchers}
    />
  );
}
