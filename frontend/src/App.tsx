import React from 'react';
import {
	AppBar,
	Toolbar,
	Typography,
	Container,
	Box,
	Button,
	Switch,
	IconButton,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';

const App: React.FC = () => {
	return (
		<div className='App'>
			<Container
				maxWidth='xs'
				style={{
					backgroundColor: '#000',
					color: '#fff',
					minHeight: '100vh',
					padding: 0,
					position: 'relative',
				}}>
				{/* 1. Header / AppBar */}
				<AppBar position='static' style={{ backgroundColor: '#333' }}>
					<Toolbar variant='dense'>
						{/* Menu or any other icon (optional) */}
						<IconButton edge='start' color='inherit' style={{ marginRight: '8px' }}>
							<MenuIcon />
						</IconButton>

						{/* Title text: e.g. "Rachel" */}
						<Typography variant='h6' style={{ flexGrow: 1 }}>
							Rachel
						</Typography>

						{/* Example right-side content (battery or time) */}
						<Typography variant='body2'>80%</Typography>
					</Toolbar>
				</AppBar>

				{/* 2. Main Content */}
				<Box
					style={{
						position: 'relative',
						width: '100%',
						height: 300,
						backgroundColor: '#222',
					}}>
					{/* Example bounding box overlay (simulating detection boxes) */}
					<Box
						style={{
							position: 'absolute',
							top: '20%',
							left: '20%',
							width: '60%',
							height: '60%',
							border: '2px solid lime',
						}}
					/>
					{/* If you have an actual video or image, place it here (e.g. <img> or <video>) */}
					{/* <img src="camera_feed.jpg" alt="Camera Feed" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> */}
				</Box>

				{/* Event info + buttons */}
				<Box style={{ padding: '16px' }}>
					<Typography variant='body1' style={{ marginBottom: '8px' }}>
						Aug 8th 4:30 PM - Front Door
					</Typography>
					<Box style={{ display: 'flex', justifyContent: 'space-between' }}>
						<Button
							variant='contained'
							style={{ backgroundColor: '#444', color: '#fff' }}>
							Full history
						</Button>
						<Button
							variant='contained'
							style={{ backgroundColor: '#444', color: '#fff' }}>
							Event details
						</Button>
					</Box>
				</Box>

				{/* 3. Bottom Controls */}
				<Box
					style={{
						position: 'fixed',
						bottom: 0,
						left: 0,
						width: '100%',
						backgroundColor: '#333',
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'space-around',
						padding: '8px 0',
					}}>
					<Button style={{ color: '#fff' }}>History</Button>
					<Switch defaultChecked color='primary' />
					<Button style={{ color: '#fff' }}>Live</Button>
				</Box>
			</Container>
		</div>
	);
};

export default App;
