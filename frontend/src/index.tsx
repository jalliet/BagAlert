import React from 'react';
import ReactDOM from 'react-dom/client';
import { SnackbarProvider } from 'notistack';
import './index.css';
import App from './App.tsx';

const rootElement = document.getElementById('root') as HTMLElement;
const root = ReactDOM.createRoot(rootElement);
root.render(
	<React.StrictMode>
		<SnackbarProvider anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
			<App />
		</SnackbarProvider>
	</React.StrictMode>
);
