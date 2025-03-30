import React, { useState } from 'react';
import {
	AppBar,
	Toolbar,
	Typography,
	Container,
	Box,
	Button,
	IconButton,
	Fab,
	Chip,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import CheckIcon from '@mui/icons-material/Check';
import WarningIcon from '@mui/icons-material/Warning';

const App: React.FC = () => {
	// State for the activated flag and selected screen
	const [activated, setActivated] = useState<boolean>(false);
	const [selectedScreen, setSelectedScreen] = useState('history');

	// Function triggered by the red exclamation mark Fab
	const callLEDs = () => {
		// Call LEDs
	};

	return (
		<div className='App'>
			<Container
				maxWidth='xl'
				style={{
					backgroundColor: '#000',
					color: '#fff',
					minHeight: '100vh',
					// width: '90vw',
					padding: 0,
					position: 'relative',
					display: 'flex',
					flexDirection: 'column',
				}}>
				{/* Header */}
				<AppBar position='static' style={{ backgroundColor: 'inherit' }}>
					<Toolbar variant='dense'>
						<IconButton edge='start' color='inherit' style={{ marginRight: '8px' }}>
							<MenuIcon />
						</IconButton>
						<Chip
							label='Live'
							size='small'
							style={{
								backgroundColor: '#333',
								color: 'green',
								fontWeight: 'bold',
								marginRight: '8px',
							}}
						/>
						<Typography variant='body2'>80%</Typography>
					</Toolbar>
				</AppBar>

				{/* Main Content Area */}
				<Box
					style={{
						flex: 1,
						padding: '16px 102px',
						overflow: 'auto',
						display: 'flex',
						flexDirection: 'column',
					}}>
					{selectedScreen === 'history' && (
						<Typography variant='body2'>History Content</Typography>
					)}
					{selectedScreen === 'live' && (
						<Box
							style={{
								flex: 1,
								position: 'relative',
								width: '100%',
								backgroundColor: '#222',
								marginTop: '8px',
								marginBottom: '170px',
							}}>
							<Box
								style={{
									position: 'absolute',
									top: '20%',
									left: '20%',
									width: '60%',
									height: '60%',
									border: `2px solid ${activated ? 'red' : 'lime'}`,
								}}
							/>
						</Box>
					)}
					{selectedScreen === 'sessions' && (
						<Typography variant='body2'>Sessions Content</Typography>
					)}
				</Box>

				{/* Bottom Controls Container */}
				<Box
					style={{
						position: 'fixed',
						bottom: 0,
						left: 0,
						width: '100%',
						display: 'flex',
						flexDirection: 'column',
						alignItems: 'center',
						gap: '8px',
						padding: '8px',
					}}>
					{/* FAB Buttons */}
					<Box
						style={{
							display: 'flex',
							justifyContent: 'center',
							gap: '16px',
							marginBottom: '15px',
						}}>
						<Fab
							onClick={callLEDs}
							style={{ backgroundColor: 'red', color: '#fff' }}
							aria-label='alert'>
							<WarningIcon />
						</Fab>
						<Fab
							onClick={() => setActivated(prev => !prev)}
							style={{ backgroundColor: 'blue', color: '#fff' }}
							aria-label='confirm'>
							<CheckIcon />
						</Fab>
					</Box>

					{/* Screen Selection Buttons */}
					<Box
						style={{
							display: 'flex',
							justifyContent: 'center',
							gap: '18px',
							paddingBottom: '18px',
						}}>
						<Button
							onClick={() => setSelectedScreen('history')}
							style={{
								backgroundColor: selectedScreen === 'history' ? '#fff' : 'transparent',
								color: selectedScreen === 'history' ? '#000' : '#fff',
								flex: 1,
							}}>
							History
						</Button>
						<Button
							onClick={() => setSelectedScreen('live')}
							style={{
								backgroundColor: selectedScreen === 'live' ? '#fff' : 'transparent',
								color: selectedScreen === 'live' ? '#000' : '#fff',
								flex: 1,
							}}>
							Live
						</Button>
						<Button
							onClick={() => setSelectedScreen('sessions')}
							style={{
								backgroundColor: selectedScreen === 'sessions' ? '#fff' : 'transparent',
								color: selectedScreen === 'sessions' ? '#000' : '#fff',
								flex: 1,
							}}>
							Sessions
						</Button>
					</Box>
				</Box>
			</Container>
		</div>
	);
};

export default App;
