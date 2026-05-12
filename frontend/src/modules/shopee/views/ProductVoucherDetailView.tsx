import ProductVoucherCreateView from './ProductVoucherCreateView';

interface ProductVoucherDetailViewProps {
  runId: number | null;
  campaignId: number | null;
  onBackToVouchers: () => void;
}

export default function ProductVoucherDetailView({ runId, campaignId, onBackToVouchers }: ProductVoucherDetailViewProps) {
  return (
    <ProductVoucherCreateView
      runId={runId}
      readOnly
      detailCampaignId={campaignId}
      onBackToVouchers={onBackToVouchers}
    />
  );
}
