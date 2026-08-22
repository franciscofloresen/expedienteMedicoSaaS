/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react';
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
import { Plus } from 'lucide-react';
import { useToast } from '../hooks/useToast';

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

/** Below this width the week grid is unreadable; the agenda (list) view is. */
const NARROW_BREAKPOINT = 768;

const isNarrow = () =>
  typeof window !== 'undefined' && window.innerWidth <= NARROW_BREAKPOINT;

export default function Agenda() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [view, setView] = useState<View>(isNarrow() ? Views.AGENDA : Views.WEEK);
  const [userPickedView, setUserPickedView] = useState(false);
  const [date, setDate] = useState(new Date());

  // Rotating an iPad crosses the breakpoint mid-consultation. Follow it — unless
  // the doctor has chosen a view, in which case their choice wins.
  useEffect(() => {
    if (userPickedView) return;
    const sync = () => setView(isNarrow() ? Views.AGENDA : Views.WEEK);
    window.addEventListener('resize', sync);
    window.addEventListener('orientationchange', sync);
    return () => {
      window.removeEventListener('resize', sync);
      window.removeEventListener('orientationchange', sync);
    };
  }, [userPickedView]);

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
      showToast('Cita programada correctamente.', 'success');
    },
    onError: () => {
      showToast('No pudimos guardar la cita. Revisa el horario e inténtalo de nuevo.', 'error');
    }
  });

  const updateMutation = useMutation({
    mutationFn: (data: {id: string, payload: Partial<CitaBase>}) => citasApi.update(data.id, data.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['citas'] });
      setIsModalOpen(false);
      showToast('Cita actualizada correctamente.', 'success');
    },
    onError: () => {
      showToast('No pudimos actualizar la cita. Inténtalo de nuevo.', 'error');
    }
  });

  const deleteMutation = useMutation({
    mutationFn: citasApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['citas'] });
      setIsModalOpen(false);
      showToast('Cita cancelada.', 'success');
    },
    onError: () => {
      showToast('No pudimos cancelar la cita. Inténtalo de nuevo.', 'error');
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
    <div className="agenda-page" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: '1rem' }}>
        <div>
          <h1 className="page-title">Agenda</h1>
          <p className="page-subtitle">Monitorea y administra tus citas</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => { setSelectedCita(null); setIsModalOpen(true); }}
        >
          <Plus size={16} /> Nueva cita
        </button>
      </div>

      <div className="agenda-shell" style={{ flex: 1, backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: '1.25rem', overflow: 'auto' }}>
        {isLoading ? (
          <div className="loading-state" style={{ height: '100%' }}>
            <div className="spinner" />
            <span>Cargando agenda médica…</span>
          </div>
        ) : (
          <Calendar
            culture="es"
            localizer={localizer}
            events={events}
            startAccessor="start"
            endAccessor="end"
            style={{ height: '100%', minHeight: 'var(--agenda-min-height, 600px)' }}
            view={view}
            onView={(newView) => { setUserPickedView(true); setView(newView); }}
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
                  color: '#04211F',
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
