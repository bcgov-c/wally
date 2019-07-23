import createRenderServer from '../src/server'
import ReactPDF, {
    Document, Page, View, Image, Text, Canvas, Link, Note, Font, StyleSheet
} from '@react-pdf/renderer'
// export all types from app.js so there is only one render path
export {
    ReactPDF, Document, Page, View, Image, Text, Canvas, Link, Note, Font, StyleSheet
}

import featureReport from './templates/featureReport';
import chart from './templates/chart';

const templates = {
    featureReport,
    chart
};

const port = process.env.PORT || 3000;

const log = (level, message) => {
    console.log(JSON.stringify({ level, message, datetime: (new Date()).toISOString() }));
};

const onReady = () => log('info', 'Server is ready');

createRenderServer(templates, log).listen(port, onReady);
