import React from 'react';
import './DownloadWidget.css';

interface DownloadWidgetProps {
    filename: string;
    size: string;
    downloadUrl: string;
    icon?: 'csv' | 'excel' | 'pdf' | 'file';
}

const DownloadWidget: React.FC<DownloadWidgetProps> = ({
    filename,
    size,
    downloadUrl,
    icon = 'csv'
}) => {
    const getIconSvg = () => {
        switch (icon) {
            case 'csv':
                return (
                    <svg className="download-icon csv" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        <text x="12" y="17" textAnchor="middle" fontSize="6" fill="currentColor" fontWeight="bold">CSV</text>
                    </svg>
                );
            case 'excel':
                return (
                    <svg className="download-icon excel" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        <text x="12" y="17" textAnchor="middle" fontSize="5" fill="currentColor" fontWeight="bold">XLS</text>
                    </svg>
                );
            default:
                return (
                    <svg className="download-icon file" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                );
        }
    };

    const handleDownload = async () => {
        try {
            const token = localStorage.getItem('access_token');
            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';

            const response = await fetch(`${baseUrl}${downloadUrl}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error('Download failed');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error('Download error:', error);
            alert('Gagal mengunduh file. Silakan coba lagi.');
        }
    };

    return (
        <div className="download-widget">
            <div className="download-widget-icon">
                {getIconSvg()}
            </div>
            <div className="download-widget-info">
                <span className="download-widget-filename">{filename}</span>
                <span className="download-widget-size">{size}</span>
            </div>
            <button
                className="download-widget-button"
                onClick={handleDownload}
                title="Download file"
            >
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    <polyline points="7,10 12,15 17,10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    <line x1="12" y1="15" x2="12" y2="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Download
            </button>
        </div>
    );
};

export default DownloadWidget;
