/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react';
import { Calendar, dateFnsLocalizer, Views } from 'react-big-calendar';
import type { View } from 'react-big-calendar';
import { format, parse, startOfWeek, getDay } from 'date-fns';
import { es } from 'date-fns/locale/es';
import 'react-big-calendar/lib/css/react-big-calendar.css';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { citasApi } from '../services/api';
import { pacientesApi } from '../services/api';
import CitaModal from '../components/CitaModal';
import type { Cita, CitaBase } from '../types';

// Setup localizer for react-big-calendar
const locales = {
  'es': es,
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales,
});

export default function Agenda() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<View>(window.innerWidth < 768 ? Views.AGENDA : Views.WEEK);
  const [date, setDate] = useState(new Date());
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedCita, setSelectedCita] = useState<Partial<Cita> | null>(null);

  // Fetch Citas
  const { data: citas = [], isLoading } = useQuery({
    queryKey: ['citas', date.toISOString()],
    queryFn: () => citasApi.getAll() // Note: For production, we'd pass start_date and end_date
  });

  // Fetch Pacientes for the dropdown
  const { data: pacientes = [] } = useQuery({
    queryKey: ['pacientes'],
    queryFn: () => pacientesApi.getAll()
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: citasApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['citas'] });
      setIsModalOpen(false);
    }
  });

  const updateMutation = useMutation({
    mutationFn: (data: {id: string, payload: Partial<CitaBase>}) => citasApi.update(data.id, data.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['citas'] });
      setIsModalOpen(false);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: citasApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['citas'] });
      setIsModalOpen(false);
    }
  });

  // Transform data for the calendar
  const events = citas.map(cita => ({
    ...cita,
    start: new Date(cita.fecha_inicio),
    end: new Date(cita.fecha_fin),
    title: cita.titulo,
  }));

  const handleSelectSlot = ({ start, end }: { start: Date, end: Date }) => {
    setSelectedCita({
      fecha_inicio: start.toISOString(),
      fecha_fin: end.toISOString(),
    });
    setIsModalOpen(true);
  };

  const handleSelectEvent = (event: any) => {
    setSelectedCita(event);
    setIsModalOpen(true);
  };

  const handleSave = (data: CitaBase) => {
    if (selectedCita?.id) {
      updateMutation.mutate({ id: selectedCita.id, payload: data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleDelete = (id: string) => {
    if (confirm('¿Estás seguro de cancelar esta cita?')) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <div style={{ height: 'calc(100vh - 4rem)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', margin: 0, color: 'var(--text-main)', fontWeight: 600 }}>Agenda Médica</h1>
          <p style={{ margin: 0, color: 'var(--text-muted)' }}>Monitorea y administra tus citas</p>
        </div>
        <button 
          onClick={() => { setSelectedCita(null); setIsModalOpen(true); }}
          style={{ backgroundColor: 'var(--primary)', color: 'white', border: 'none', padding: '0.75rem 1.5rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 500 }}
        >
          + Nueva Cita
        </button>
      </div>

      <div style={{ flex: 1, backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '1.5rem', boxShadow: 'var(--shadow-sm)', overflow: 'auto' }}>
        {isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            Cargando agenda...
          </div>
        ) : (
          <Calendar
            culture="es"
            localizer={localizer}
            events={events}
            startAccessor="start"
            endAccessor="end"
            style={{ height: '100%', minHeight: '600px', minWidth: '800px' }}
            view={view}
            onView={(newView) => setView(newView)}
            date={date}
            onNavigate={(newDate) => setDate(newDate)}
            selectable
            onSelectSlot={handleSelectSlot}
            onSelectEvent={handleSelectEvent}
            messages={{
              next: "Sig",
              previous: "Ant",
              today: "Hoy",
              month: "Mes",
              week: "Semana",
              day: "Día",
              agenda: "Lista"
            }}
            eventPropGetter={() => {
              return {
                style: {
                  backgroundColor: 'var(--primary)',
                  borderRadius: '6px',
                  border: 'none',
                  color: 'white',
                  fontSize: '0.875rem'
                }
              };
            }}
          />
        )}
      </div>

      <CitaModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSave}
        onDelete={handleDelete}
        cita={selectedCita}
        pacientes={pacientes as any}
        citas={citas as any}
      />
      
    </div>
  );
}
