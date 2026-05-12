import PrivateVoucherCreateView from './PrivateVoucherCreateView';

interface PrivateVoucherDetailViewProps {
  runId: number | null;
  campaignId: number | null;
  onBackToVouchers: () => void;
}

export default function PrivateVoucherDetailView({ runId, campaignId, onBackToVouchers }: PrivateVoucherDetailViewProps) {
  return (
    <PrivateVoucherCreateView
      runId={runId}
      readOnly
      detailCampaignId={campaignId}
      onBackToVouchers={onBackToVouchers}
    />
  );
}
